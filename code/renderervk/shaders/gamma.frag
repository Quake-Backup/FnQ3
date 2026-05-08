#version 450

layout(set = 0, binding = 0) uniform sampler2D texture0;

layout(location = 0) in vec2 frag_tex_coord;

layout(location = 0) out vec4 out_color;

layout(constant_id = 0) const float gamma = 1.0;
layout(constant_id = 1) const float obScale = 2.0;
layout(constant_id = 2) const float greyscale = 0.0;
//
layout(constant_id = 7) const int ditherMode = 0; // 0 - disabled, 1 - ordered
layout(constant_id = 8) const int depth_r = 255;
layout(constant_id = 9) const int depth_g = 255;
layout(constant_id = 10) const int depth_b = 255;
layout(constant_id = 11) const int outputColorSpace = 0; // 0 - SDR, 1 - HDR10 ST2084
layout(constant_id = 12) const float hdrPaperWhiteNits = 203.0;
layout(constant_id = 13) const float hdrMaxNits = 1000.0;
layout(constant_id = 14) const int toneMapMode = 0; // 0 - legacy, 1 - Reinhard, 2 - ACES fit
layout(constant_id = 15) const float toneMapExposure = 1.0;

const vec3 sRGB = { 0.2126, 0.7152, 0.0722 };

const int bayerSize = 8;
const float bayerMatrix[bayerSize * bayerSize] = {
	0,  32, 8,  40, 2,  34, 10, 42,
	48, 16, 56, 24, 50, 18, 58, 26,
	12, 44, 4,  36, 14, 46, 6,  38,
	60, 28, 52, 20, 62, 30, 54, 22,
	3,  35, 11, 43, 1,  33, 9,  41,
	51, 19, 59, 27, 49, 17, 57, 25,
	15, 47, 7,  39, 13, 45, 5,  37,
	63, 31, 55, 23, 61, 29, 53, 21
};

float threshold() {
	ivec2 coordDenormalized = ivec2(gl_FragCoord.xy);
	ivec2 bayerCoord = coordDenormalized % bayerSize;
	float bayerSample = bayerMatrix[bayerCoord.x + bayerCoord.y * bayerSize];
	float threshold = (bayerSample + 0.5) / float(bayerSize * bayerSize);
	return threshold;
}

vec3 dither(vec3 color) {
	ivec3 depth = ivec3(depth_r, depth_g, depth_b);
	vec3 cDenormalized = color * depth;
	vec3 cLow = floor(cDenormalized);
	vec3 cFractional = cDenormalized - cLow;
	vec3 cDithered = cLow + step(threshold(), cFractional);
	return cDithered / depth;
}

vec3 srgbToLinear(vec3 color) {
	vec3 linearLow = color / 12.92;
	vec3 linearHigh = pow((color + vec3(0.055)) / 1.055, vec3(2.4));
	return mix(linearLow, linearHigh, step(vec3(0.04045), color));
}

vec3 linearSrgbToBt2020(vec3 color) {
	return vec3(
		dot(color, vec3(0.6274040, 0.3292820, 0.0433136)),
		dot(color, vec3(0.0690970, 0.9195400, 0.0113612)),
		dot(color, vec3(0.0163916, 0.0880132, 0.8955950))
	);
}

vec3 pqEncodeNits(vec3 nits) {
	const float m1 = 0.1593017578125;
	const float m2 = 78.84375;
	const float c1 = 0.8359375;
	const float c2 = 18.8515625;
	const float c3 = 18.6875;
	vec3 y = pow(clamp(nits, vec3(0.0), vec3(hdrMaxNits)) / 10000.0, vec3(m1));
	return pow((c1 + c2 * y) / (1.0 + c3 * y), vec3(m2));
}

vec3 encodeHdr10(vec3 color) {
	vec3 linearSrgb = srgbToLinear(max(color, vec3(0.0)));
	vec3 bt2020 = max(linearSrgbToBt2020(linearSrgb), vec3(0.0));
	return pqEncodeNits(bt2020 * hdrPaperWhiteNits);
}

vec3 toneMapReinhard(vec3 color) {
	color = max(color * max(toneMapExposure, 0.0), vec3(0.0));
	return color / (vec3(1.0) + color);
}

vec3 toneMapAces(vec3 color) {
	const float a = 2.51;
	const float b = 0.03;
	const float c = 2.43;
	const float d = 0.59;
	const float e = 0.14;
	color = max(color * max(toneMapExposure, 0.0), vec3(0.0));
	return clamp((color * (a * color + b)) / (color * (c * color + d) + e), vec3(0.0), vec3(1.0));
}

vec3 applyToneMap(vec3 color) {
	if ( toneMapMode == 1 ) {
		return toneMapReinhard(color);
	}
	if ( toneMapMode == 2 ) {
		return toneMapAces(color);
	}
	return color;
}

void main() {
	vec3 base = texture(texture0, frag_tex_coord).rgb;
	vec3 color;

	if ( greyscale == 1 )
	{
		base = vec3(dot(base, sRGB));
	}
	else if ( greyscale != 0 )
	{
		vec3 luma = vec3(dot(base, sRGB));
		base = mix(base, luma, greyscale);
	}

	if ( gamma != 1.0 )
	{
		color = pow(base, vec3(gamma)) * obScale;
	}
	else
	{
		color = base * obScale;
	}

	color = applyToneMap(color);

	if ( outputColorSpace == 1 ) {
		color = encodeHdr10(color);
	} else if ( ditherMode == 1 ) {
		color = dither(color);
	}

	out_color = vec4(color, 1);
}
