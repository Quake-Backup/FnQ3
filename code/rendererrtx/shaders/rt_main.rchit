#version 460
#extension GL_EXT_ray_tracing : require
#extension GL_EXT_nonuniform_qualifier : require

const float PI = 3.14159265359;
const uint RTX_RT_COLORSPACE_SRGB = 1u;
const uint RTX_RT_MAX_SCENE_TEXTURES = 2048u;
const uint RTX_RT_INVALID_TEXTURE_INDEX = 0xFFFFFFFFu;
const uint RTX_RT_MATFLAG_MASKED = 1u << 0;
const uint RTX_RT_MATFLAG_EMISSIVE = 1u << 1;
const uint RTX_RT_MATFLAG_TRANSLUCENT = 1u << 2;
const uint RTX_RT_MATFLAG_PARTICLE = 1u << 6;
const uint RTX_RT_MATFLAG_EFFECT = 1u << 7;
const uint RTX_RT_MODE_FLAG_PARTICLE_VOLUME = 1u << 3;
const uint RTX_RT_PAYLOAD_FLAG_HIT = 1u << 0;
const uint RTX_RT_PAYLOAD_FLAG_DYNAMIC = 1u << 1;

struct RtRadiancePayload {
	vec3 color;
	float hitT;
	vec3 normal;
	uint flags;
};

struct RtPackedVertex {
	vec4 xyz;
	vec4 normal;
	vec4 tangent;
	vec2 texCoord;
	uint color;
	uint materialIndex;
};

struct RtGpuMaterial {
	vec4 baseColor;
	vec4 emissiveColorScale;
	vec4 pbrParams;
	uvec4 metadata;
	uvec4 textureInfo;
};

struct RtLight {
	vec4 positionRadius;
	vec4 colorType;
	vec4 directionSoftness;
};

layout(location = 0) rayPayloadInEXT RtRadiancePayload payloadRadiance;
layout(location = 1) rayPayloadEXT uint payloadShadow;
hitAttributeEXT vec2 barycentrics;

layout(set = 0, binding = 0) uniform accelerationStructureEXT u_tlas;
layout(set = 0, binding = 2, std430) readonly buffer RtWorldVertexBuffer {
	RtPackedVertex vertices[];
} u_worldVertices;
layout(set = 0, binding = 3, std430) readonly buffer RtWorldIndexBuffer {
	uint indices[];
} u_worldIndices;
layout(set = 0, binding = 4, std430) readonly buffer RtWorldMaterialBuffer {
	RtGpuMaterial materials[];
} u_worldMaterials;
layout(set = 0, binding = 5, std430) readonly buffer RtDynamicVertexBuffer {
	RtPackedVertex vertices[];
} u_dynamicVertices;
layout(set = 0, binding = 6, std430) readonly buffer RtDynamicIndexBuffer {
	uint indices[];
} u_dynamicIndices;
layout(set = 0, binding = 7, std430) readonly buffer RtDynamicMaterialBuffer {
	RtGpuMaterial materials[];
} u_dynamicMaterials;
layout(set = 0, binding = 8, std430) readonly buffer RtLightBuffer {
	RtLight lights[];
} u_lights;
layout(set = 0, binding = 11, std430) readonly buffer RtTemporalParamsBuffer {
	vec4 prevCameraOriginTanHalfFovX;
	vec4 prevCameraForwardTanHalfFovY;
	vec4 prevCameraRightWidth;
	vec4 prevCameraUpHeight;
	vec4 dynamicMotionAndExposure;
	vec4 temporalParams0;
	vec4 denoiseParams;
	vec4 exposureParams;
	vec4 legacyColorParams;
	vec4 readabilityParams;
	uvec4 modes;
} u_temporal;
layout(set = 0, binding = 13) uniform sampler2D u_sceneTextures[RTX_RT_MAX_SCENE_TEXTURES];

layout(push_constant) uniform RtPushConstants {
	vec4 cameraOriginTanHalfFovX;
	vec4 cameraForwardTanHalfFovY;
	vec4 cameraRightWidth;
	vec4 cameraUpHeight;
	vec4 sunDirection;
	vec4 sunColorIntensity;
	uint debugMode;
	uint frameIndex;
	uint activeInstances;
	uint lightCount;
	uint worldMaterialCount;
	uint dynamicMaterialCount;
	uint shadowMode;
	float shadowSoftness;
	float indirectStrength;
	float reflectionStrength;
	float skyIntensity;
	float refractionIor;
	float sunIntensity;
	uint refractiveMode;
	uint indirectBounce;
} pc;

uint hash_u32(uint x)
{
	x ^= x >> 16;
	x *= 0x7feb352du;
	x ^= x >> 15;
	x *= 0x846ca68bu;
	x ^= x >> 16;
	return x;
}

uint hash_world_cell(vec3 p)
{
	ivec3 cell = ivec3(floor(p * 0.25));
	uint h = hash_u32(uint(cell.x) * 73856093u);
	h = hash_u32(h ^ (uint(cell.y) * 19349663u));
	h = hash_u32(h ^ (uint(cell.z) * 83492791u));
	return h;
}

float rand01(inout uint state)
{
	state = hash_u32(state + 0x9e3779b9u);
	return float(state & 0x00FFFFFFu) / float(0x01000000u);
}

vec3 hash_color(uint value)
{
	uint x = value * 1664525u + 1013904223u;
	return vec3(
		float((x >> 0) & 255u),
		float((x >> 8) & 255u),
		float((x >> 16) & 255u)) / 255.0;
}

vec3 heatmap(float t)
{
	t = clamp(t, 0.0, 1.0);
	return vec3(
		smoothstep(0.45, 1.0, t),
		smoothstep(0.0, 0.65, t) * (1.0 - smoothstep(0.65, 1.0, t)),
		1.0 - smoothstep(0.0, 0.55, t));
}

void basis_from_dir(vec3 n, out vec3 tangent, out vec3 bitangent)
{
	vec3 up = abs(n.z) < 0.999 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
	tangent = normalize(cross(up, n));
	bitangent = cross(n, tangent);
}

vec3 sample_cone(vec3 dir, float coneAngle, inout uint rngState)
{
	if (coneAngle <= 1e-4) {
		return normalize(dir);
	}

	float u = rand01(rngState);
	float v = rand01(rngState);
	float cosTheta = mix(cos(coneAngle), 1.0, u);
	float sinTheta = sqrt(max(0.0, 1.0 - cosTheta * cosTheta));
	float phi = 2.0 * PI * v;
	vec3 t;
	vec3 b;
	basis_from_dir(normalize(dir), t, b);
	return normalize(t * cos(phi) * sinTheta + b * sin(phi) * sinTheta + dir * cosTheta);
}

vec3 sample_cosine_hemisphere(vec3 normal, inout uint rngState)
{
	float u1 = rand01(rngState);
	float u2 = rand01(rngState);
	float r = sqrt(u1);
	float theta = 2.0 * PI * u2;
	float x = r * cos(theta);
	float y = r * sin(theta);
	float z = sqrt(max(0.0, 1.0 - u1));
	vec3 t;
	vec3 b;
	basis_from_dir(normal, t, b);
	return normalize(t * x + b * y + normal * z);
}

vec3 evaluate_environment(vec3 rayDir)
{
	float up = clamp(rayDir.z * 0.5 + 0.5, 0.0, 1.0);
	vec3 sunColor = max(pc.sunColorIntensity.rgb * pc.sunIntensity, vec3(0.0));
	float sunLuma = max(dot(sunColor, vec3(0.2126, 0.7152, 0.0722)), 1e-4);
	vec3 sunTint = sunColor / sunLuma;
	vec3 skyBottom = mix(vec3(0.040, 0.050, 0.070), sunTint * 0.070, 0.55);
	vec3 skyTop = mix(vec3(0.24, 0.33, 0.52), sunTint * 0.300, 0.75);
	vec3 skyColor = mix(skyBottom, skyTop, up) * pc.skyIntensity;
	vec3 sunDir = normalize(pc.sunDirection.xyz);
	float sunDisk = pow(max(dot(rayDir, sunDir), 0.0), 320.0);
	return skyColor + sunColor * sunDisk;
}

uint fetch_index(uint geometryClass, uint index)
{
	return geometryClass == 0u ? u_worldIndices.indices[index] : u_dynamicIndices.indices[index];
}

RtPackedVertex fetch_vertex(uint geometryClass, uint index)
{
	return geometryClass == 0u ? u_worldVertices.vertices[index] : u_dynamicVertices.vertices[index];
}

RtGpuMaterial fetch_material(uint geometryClass, uint index)
{
	uint maxCount = geometryClass == 0u ? max(pc.worldMaterialCount, 1u) : max(pc.dynamicMaterialCount, 1u);
	uint clamped = min(index, maxCount - 1u);
	return geometryClass == 0u ? u_worldMaterials.materials[clamped] : u_dynamicMaterials.materials[clamped];
}

float DistributionGGX(float NdotH, float roughness)
{
	float a = roughness * roughness;
	float a2 = a * a;
	float denom = (NdotH * NdotH) * (a2 - 1.0) + 1.0;
	return a2 / max(PI * denom * denom, 1e-5);
}

float GeometrySchlickGGX(float NdotV, float roughness)
{
	float k = (roughness + 1.0);
	k = (k * k) / 8.0;
	return NdotV / max(NdotV * (1.0 - k) + k, 1e-5);
}

float GeometrySmith(float NdotV, float NdotL, float roughness)
{
	float ggx1 = GeometrySchlickGGX(NdotV, roughness);
	float ggx2 = GeometrySchlickGGX(NdotL, roughness);
	return ggx1 * ggx2;
}

vec3 FresnelSchlick(float cosTheta, vec3 F0)
{
	return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

float trace_shadow_visibility(vec3 origin, vec3 direction, float maxT)
{
	payloadShadow = 0u;
	traceRayEXT(
		u_tlas,
		gl_RayFlagsOpaqueEXT | gl_RayFlagsTerminateOnFirstHitEXT | gl_RayFlagsSkipClosestHitShaderEXT,
		0xFF,
		0,
		0,
		1,
		origin,
		0.01,
		direction,
		maxT,
		1);
	return float(payloadShadow);
}

void main()
{
	uint geometryClass = gl_InstanceCustomIndexEXT == 1u ? 1u : 0u;
	uint triBase = gl_PrimitiveID * 3u;
	uint i0 = fetch_index(geometryClass, triBase + 0u);
	uint i1 = fetch_index(geometryClass, triBase + 1u);
	uint i2 = fetch_index(geometryClass, triBase + 2u);
	RtPackedVertex v0 = fetch_vertex(geometryClass, i0);
	RtPackedVertex v1 = fetch_vertex(geometryClass, i1);
	RtPackedVertex v2 = fetch_vertex(geometryClass, i2);
	float b1 = barycentrics.x;
	float b2 = barycentrics.y;
	float b0 = max(0.0, 1.0 - b1 - b2);
	vec3 worldPos = v0.xyz.xyz * b0 + v1.xyz.xyz * b1 + v2.xyz.xyz * b2;
	vec3 normal = normalize(v0.normal.xyz * b0 + v1.normal.xyz * b1 + v2.normal.xyz * b2);
	vec2 uv = v0.texCoord * b0 + v1.texCoord * b1 + v2.texCoord * b2;
	vec3 vertexColor =
		unpackUnorm4x8(v0.color).rgb * b0 +
		unpackUnorm4x8(v1.color).rgb * b1 +
		unpackUnorm4x8(v2.color).rgb * b2;
	RtGpuMaterial material = fetch_material(geometryClass, v0.materialIndex);
	vec4 albedoSample = vec4(1.0);
	uint albedoTextureIndex = material.textureInfo.x;
	bool hasAlbedoTexture = albedoTextureIndex != RTX_RT_INVALID_TEXTURE_INDEX && albedoTextureIndex < RTX_RT_MAX_SCENE_TEXTURES;
	if (hasAlbedoTexture) {
		albedoSample = texture(u_sceneTextures[nonuniformEXT(albedoTextureIndex)], uv);
		if (material.metadata.y == RTX_RT_COLORSPACE_SRGB) {
			albedoSample.rgb = pow(max(albedoSample.rgb, vec3(0.0)), vec3(2.2));
		}
	}
	vec3 albedo = material.baseColor.rgb * albedoSample.rgb;
	float materialAlpha = clamp(material.baseColor.a * albedoSample.a, 0.0, 1.0);
	float roughness = clamp(material.pbrParams.x, 0.04, 1.0);
	float metallic = clamp(material.pbrParams.y, 0.0, 1.0);
	float alphaCutoff = clamp(material.pbrParams.z, 0.0, 1.0);
	uint materialFlags = material.metadata.x;
	vec3 emissive = material.emissiveColorScale.rgb * material.emissiveColorScale.w;
	if ((materialFlags & RTX_RT_MATFLAG_EFFECT) != 0u) {
		vec3 tint = max(vertexColor, vec3(0.05));
		albedo *= tint;
		emissive *= tint;
	}
	albedo = clamp(albedo, 0.0, 1.0);
	vec3 V = normalize(-gl_WorldRayDirectionEXT);
	vec3 N = normalize(normal);
	float NdotV;
	vec3 F0 = mix(vec3(0.04), albedo, metallic);
	vec3 Lo = vec3(0.0);
	uint contributingLights = 0u;
	uint seed = hash_u32(gl_PrimitiveID * 7477u + gl_InstanceCustomIndexEXT * 341u + pc.frameIndex * 1597u);
	seed = hash_u32(seed ^ hash_world_cell(worldPos) ^ floatBitsToUint(gl_HitTEXT));

	if (dot(N, V) < 0.0) {
		N = -N;
	}
	NdotV = max(dot(N, V), 0.0);

	payloadRadiance.hitT = gl_HitTEXT;
	payloadRadiance.normal = N;
	payloadRadiance.flags = RTX_RT_PAYLOAD_FLAG_HIT | (geometryClass == 1u ? RTX_RT_PAYLOAD_FLAG_DYNAMIC : 0u);

	if ((materialFlags & RTX_RT_MATFLAG_MASKED) != 0u && alphaCutoff > 0.0) {
		float alpha = materialAlpha;
		if (!hasAlbedoTexture) {
			alpha = fract(uv.x * 17.0 + uv.y * 29.0);
		}
		if (alpha < alphaCutoff) {
			payloadRadiance.color = evaluate_environment(normalize(gl_WorldRayDirectionEXT));
			payloadRadiance.hitT = 0.0;
			payloadRadiance.flags = 0u;
			return;
		}
	}

	for (uint lightIndex = 0u; lightIndex < pc.lightCount; lightIndex++) {
		RtLight light = u_lights.lights[lightIndex];
		vec3 lightColor = max(light.colorType.rgb, vec3(0.0));
		vec3 L;
		float radianceScale = 1.0;
		float maxT = 100000.0;
		float NdotL;
		float visibility = 1.0;

		if (light.colorType.w > 0.5) {
			L = normalize(-light.directionSoftness.xyz);
		} else {
			vec3 toLight = light.positionRadius.xyz - worldPos;
			float dist = length(toLight);
			float radius = max(light.positionRadius.w, 0.001);
			float invRadius = 1.0 / radius;
			if (dist >= radius || dist <= 1e-4) {
				continue;
			}
			L = toLight / dist;
			{
				float edge = max(1.0 - dist * invRadius, 0.0);
				float falloff = edge * edge;
				float distAtten = 1.0 / (1.0 + (dist * dist) * (invRadius * invRadius) * 2.0);
				radianceScale = falloff * distAtten;
			}
			maxT = dist - 0.02;
		}

		NdotL = max(dot(N, L), 0.0);
		if (NdotL <= 0.0) {
			continue;
		}

		if (pc.shadowMode > 0u) {
			if (pc.shadowMode > 1u) {
				float coneAngle = clamp(light.directionSoftness.w, 0.0, 1.0);
				vec3 shadowDir0;
				vec3 shadowDir1;
				float vis0;
				float vis1;
				coneAngle *= (light.colorType.w > 0.5) ? 0.02 : 0.18;
				shadowDir0 = sample_cone(L, coneAngle, seed);
				shadowDir1 = sample_cone(L, coneAngle, seed);
				vis0 = trace_shadow_visibility(worldPos + N * 0.01, shadowDir0, maxT);
				vis1 = trace_shadow_visibility(worldPos + N * 0.01, shadowDir1, maxT);
				visibility = 0.5 * (vis0 + vis1);
			} else {
				visibility = trace_shadow_visibility(worldPos + N * 0.01, L, maxT);
			}
			if (visibility <= 0.001) {
				continue;
			}
		}

		vec3 H = normalize(V + L);
		float NdotH = max(dot(N, H), 0.0);
		float VdotH = max(dot(V, H), 0.0);
		float D = DistributionGGX(NdotH, roughness);
		float G = GeometrySmith(NdotV, NdotL, roughness);
		vec3 F = FresnelSchlick(VdotH, F0);
		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 1e-5);
		vec3 kS = F;
		vec3 kD = (vec3(1.0) - kS) * (1.0 - metallic);
		vec3 radiance = lightColor * radianceScale;

		Lo += (kD * albedo / PI + specular) * radiance * NdotL * visibility;
		contributingLights++;
	}

	{
		vec3 reflectDir = reflect(-V, N);
		float coneAngle = roughness * roughness * 0.6;
		vec3 glossyDir = sample_cone(reflectDir, coneAngle, seed);
		vec3 envSpec = evaluate_environment(glossyDir);
		vec3 F = FresnelSchlick(NdotV, F0);
		Lo += envSpec * F * pc.reflectionStrength;
	}

	if (pc.indirectBounce != 0u) {
		vec3 diffuseDir = sample_cosine_hemisphere(N, seed);
		float indirectVis = 1.0;
		if (pc.shadowMode > 0u) {
			indirectVis = trace_shadow_visibility(worldPos + N * 0.01, diffuseDir, 100000.0);
		}
		Lo += evaluate_environment(diffuseDir) * (albedo * (1.0 - metallic)) * pc.indirectStrength * indirectVis;
	}

	Lo += emissive;

	if ((materialFlags & RTX_RT_MATFLAG_PARTICLE) != 0u &&
		(u_temporal.modes.w & RTX_RT_MODE_FLAG_PARTICLE_VOLUME) != 0u) {
		float viewFacing = clamp(1.0 - abs(dot(N, V)), 0.0, 1.0);
		float density = clamp(material.baseColor.a, 0.15, 0.9);
		vec3 phaseTint = mix(vec3(0.35), albedo, 0.75);
		vec3 envScatter = evaluate_environment(-V) * (0.35 + 0.65 * viewFacing);
		vec3 scatter = (envScatter + Lo * 0.35) * phaseTint * (0.5 + 0.5 * density);
		Lo = mix(Lo, scatter + emissive, 0.65);
	}

	if ((materialFlags & RTX_RT_MATFLAG_TRANSLUCENT) != 0u && pc.refractiveMode > 0u) {
		float alpha = clamp(material.baseColor.a, 0.05, 0.95);
		vec3 transmissionDir = -V;
		if (pc.refractiveMode > 1u) {
			vec3 refracted = refract(-V, N, 1.0 / max(pc.refractionIor, 1.0));
			if (length(refracted) > 1e-4) {
				transmissionDir = refracted;
			}
		}
		{
			vec3 transmission = evaluate_environment(normalize(transmissionDir)) * albedo;
			vec3 F = FresnelSchlick(NdotV, vec3(0.04));
			float blend = clamp((F.r * 0.7) + alpha * 0.3, 0.05, 0.95);
			Lo = mix(transmission, Lo, blend);
		}
	}

	if (pc.debugMode == 1u) {
		payloadRadiance.color = hash_color(gl_InstanceCustomIndexEXT + 1u);
		return;
	}
	if (pc.debugMode == 2u) {
		float b2 = max(0.0, 1.0 - barycentrics.x - barycentrics.y);
		payloadRadiance.color = vec3(barycentrics.x, barycentrics.y, b2);
		return;
	}
	if (pc.debugMode == 3u) {
		payloadRadiance.color = N * 0.5 + 0.5;
		return;
	}
	if (pc.debugMode == 4u) {
		payloadRadiance.color = albedo;
		return;
	}
	if (pc.debugMode == 5u) {
		payloadRadiance.color = vec3(roughness);
		return;
	}
	if (pc.debugMode == 6u) {
		payloadRadiance.color = emissive;
		return;
	}
	if (pc.debugMode == 7u) {
		float t = float(contributingLights) / max(float(pc.lightCount), 1.0);
		payloadRadiance.color = heatmap(t);
		return;
	}
	if (pc.debugMode == 8u) {
		payloadRadiance.color = vec3(metallic);
		return;
	}

	payloadRadiance.color = max(Lo, vec3(0.0));
	payloadRadiance.normal = N;
}
