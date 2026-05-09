#version 450

layout(set = 0, binding = 0) uniform sampler2D texture0;
layout(set = 1, binding = 0) uniform sampler2D colorGradeLut;

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
layout(constant_id = 17) const int sceneLinearMode = 0;
layout(constant_id = 18) const int colorGradeMode = 0; // 0 - none, 1 - LGG, 2 - 3D LUT atlas, 3 - both
layout(constant_id = 19) const float gradeLiftR = 0.0;
layout(constant_id = 20) const float gradeLiftG = 0.0;
layout(constant_id = 21) const float gradeLiftB = 0.0;
layout(constant_id = 22) const float gradeGammaR = 1.0;
layout(constant_id = 23) const float gradeGammaG = 1.0;
layout(constant_id = 24) const float gradeGammaB = 1.0;
layout(constant_id = 25) const float gradeGainR = 1.0;
layout(constant_id = 26) const float gradeGainG = 1.0;
layout(constant_id = 27) const float gradeGainB = 1.0;
layout(constant_id = 28) const float whitePoint00 = 1.0;
layout(constant_id = 29) const float whitePoint01 = 0.0;
layout(constant_id = 30) const float whitePoint02 = 0.0;
layout(constant_id = 31) const float whitePoint10 = 0.0;
layout(constant_id = 32) const float whitePoint11 = 1.0;
layout(constant_id = 33) const float whitePoint12 = 0.0;
layout(constant_id = 34) const float whitePoint20 = 0.0;
layout(constant_id = 35) const float whitePoint21 = 0.0;
layout(constant_id = 36) const float whitePoint22 = 1.0;
layout(constant_id = 37) const int colorGradeLutSize = 0;
layout(constant_id = 38) const float colorGradeLutScale = 4.0;

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
	color = max(color, vec3(0.0));
	return color / (vec3(1.0) + color);
}

vec3 toneMapAces(vec3 color) {
	const float a = 2.51;
	const float b = 0.03;
	const float c = 2.43;
	const float d = 0.59;
	const float e = 0.14;
	color = max(color, vec3(0.0));
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

vec3 applyLiftGammaGainAndWhitePoint(vec3 color) {
	vec3 lift = vec3(gradeLiftR, gradeLiftG, gradeLiftB);
	vec3 invGamma = 1.0 / max(vec3(gradeGammaR, gradeGammaG, gradeGammaB), vec3(0.0001));
	vec3 gain = vec3(gradeGainR, gradeGainG, gradeGainB);
	mat3 whitePoint = mat3(
		whitePoint00, whitePoint10, whitePoint20,
		whitePoint01, whitePoint11, whitePoint21,
		whitePoint02, whitePoint12, whitePoint22
	);

	color = max(color + lift, vec3(0.0));
	color = pow(color, invGamma) * gain;
	return max(whitePoint * color, vec3(0.0));
}

vec3 sampleColorGradeLut(vec3 color) {
	if ( colorGradeLutSize < 2 ) {
		return color;
	}

	float lutSize = float(colorGradeLutSize);
	float lutMax = max(colorGradeLutScale, 1.0);
	vec3 coord = clamp(color / lutMax, vec3(0.0), vec3(1.0)) * (lutSize - 1.0);
	float slice0 = floor(coord.b);
	float slice1 = min(slice0 + 1.0, lutSize - 1.0);
	float fracB = coord.b - slice0;
	float atlasWidth = lutSize * lutSize;
	vec2 uv0 = vec2((slice0 * lutSize + coord.r + 0.5) / atlasWidth, (coord.g + 0.5) / lutSize);
	vec2 uv1 = vec2((slice1 * lutSize + coord.r + 0.5) / atlasWidth, uv0.y);
	vec3 graded = mix(texture(colorGradeLut, uv0).rgb, texture(colorGradeLut, uv1).rgb, fracB);
	return graded * lutMax;
}

vec3 applyColorGrade(vec3 color) {
	if ( colorGradeMode == 1 || colorGradeMode == 3 ) {
		color = applyLiftGammaGainAndWhitePoint(color);
	}
	if ( colorGradeMode == 2 || colorGradeMode == 3 ) {
		color = sampleColorGradeLut(color);
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

	if ( sceneLinearMode != 0 ) {
		color = max(base * obScale * max(toneMapExposure, 0.0), vec3(0.0));
		color = applyColorGrade(color);
		color = applyToneMap(color);
	} else {
		if ( gamma != 1.0 )
		{
			color = pow(max(base, vec3(0.0)), vec3(gamma)) * obScale;
		}
		else
		{
			color = base * obScale;
		}
	}

	if ( outputColorSpace == 1 ) {
		color = encodeHdr10(color);
	} else if ( ditherMode == 1 ) {
		color = dither(color);
	}

	out_color = vec4(color, 1);
}
