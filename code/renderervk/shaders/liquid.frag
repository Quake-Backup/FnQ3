#version 450

layout(set = 0, binding = 0) uniform LiquidUniforms {
	vec4 eye_pos;
	vec4 liquid_params;              // time, warp pixels, pass strength, inverse target width
	vec4 liquid_info;                // type scale, impulse count, inverse target height, refraction pass
	vec4 liquid_impulse[8];          // local xyz, expanding ring radius
	vec4 liquid_amplitude[2];        // eight packed amplitudes
};

layout(set = 1, binding = 0) uniform sampler2D scene_color;

layout(location = 0) in vec4 frag_screen;
layout(location = 1) in vec3 frag_position;
layout(location = 2) in vec3 frag_normal;
layout(location = 3) in vec3 frag_view;

layout(location = 0) out vec4 out_color;

float ImpulseAmplitude(int index)
{
	return index < 4 ? liquid_amplitude[0][index] : liquid_amplitude[1][index - 4];
}

void main()
{
	vec3 normal = normalize(frag_normal);
	vec3 view_dir = normalize(frag_view);

	float fresnel = 1.0 - abs(dot(normal, view_dir));
	fresnel *= fresnel;
	if (liquid_info.w > 0.5) {
		vec2 inverse_view = vec2(liquid_params.w, liquid_info.z);
		vec2 uv = frag_screen.xy / frag_screen.w;
		vec2 ambient_pixels;
		vec2 ripple_pixels = vec2(0.0);

		ambient_pixels.x = sin(dot(frag_position, vec3(0.031, 0.017, 0.0)) + liquid_params.x * 1.13);
		ambient_pixels.y = sin(dot(frag_position, vec3(-0.013, 0.027, 0.019)) - liquid_params.x * 0.87);
		ambient_pixels *= clamp(liquid_params.y, 0.0, 8.0);

		int impulse_count = clamp(int(liquid_info.y + 0.5), 0, 8);
		for (int i = 0; i < impulse_count; ++i) {
			vec3 delta = frag_position - liquid_impulse[i].xyz;
			float height = dot(delta, normal);
			vec3 tangent_delta = delta - normal * height;
			float distance_to_center = length(tangent_delta);
			float radius = liquid_impulse[i].w;
			float width = 20.0 + radius * 0.12;
			float ring = 1.0 - clamp(abs(distance_to_center - radius) / width, 0.0, 1.0);
			float height_fade = 1.0 - clamp(abs(height) / max(48.0, width * 3.0), 0.0, 1.0);
			vec2 screen_gradient = vec2(dFdx(distance_to_center), dFdy(distance_to_center));
			float gradient_length = length(screen_gradient);
			vec2 direction = gradient_length > 0.0001 ? screen_gradient / gradient_length : vec2(0.0);
			ripple_pixels += direction * ring * height_fade * ImpulseAmplitude(i) * 3.0;
		}

		vec2 edge = smoothstep(vec2(0.0), vec2(0.06), uv)
			* smoothstep(vec2(0.0), vec2(0.06), vec2(1.0) - uv);
		float edge_fade = min(edge.x, edge.y);
		vec2 sample_uv = clamp(uv + (ambient_pixels + ripple_pixels) * inverse_view * edge_fade,
			vec2(0.002), vec2(0.998));
		vec3 scene = texture(scene_color, sample_uv).rgb;
		float alpha = liquid_info.x * clamp(liquid_params.z, 0.0, 1.0);
		out_color = vec4(scene, alpha);
	} else {
		vec3 sheen_color = liquid_info.x > 0.8 ? vec3(0.42, 0.58, 0.70)
			: (liquid_info.x > 0.4 ? vec3(0.30, 0.55, 0.18) : vec3(0.95, 0.38, 0.08));
		float alpha = liquid_info.x * clamp(liquid_params.z, 0.0, 1.0)
			* clamp(0.03 + fresnel * 0.27, 0.0, 0.30);
		out_color = vec4(sheen_color, alpha);
	}
}
