#version 460
#extension GL_EXT_ray_tracing : require

struct RtRadiancePayload {
	vec3 color;
	float hitT;
	vec3 normal;
	uint flags;
};

layout(location = 0) rayPayloadInEXT RtRadiancePayload payloadRadiance;

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

void main()
{
	vec3 rayDir = normalize(gl_WorldRayDirectionEXT);
	float up = clamp(rayDir.z * 0.5 + 0.5, 0.0, 1.0);
	vec3 skyBottom = vec3(0.055, 0.070, 0.090);
	vec3 skyTop = vec3(0.32, 0.44, 0.67);
	vec3 skyColor = mix(skyBottom, skyTop, up) * pc.skyIntensity;
	vec3 sunDir = normalize(pc.sunDirection.xyz);
	vec3 sunColor = pc.sunColorIntensity.rgb * pc.sunIntensity;
	float sunDisk = pow(max(dot(rayDir, sunDir), 0.0), 320.0);
	vec3 environment = skyColor + sunColor * sunDisk;

	payloadRadiance.color = environment;
	payloadRadiance.hitT = 0.0;
	payloadRadiance.normal = vec3(0.0, 0.0, 1.0);
	payloadRadiance.flags = 0u;
}
