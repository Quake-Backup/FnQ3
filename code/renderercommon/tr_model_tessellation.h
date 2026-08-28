#ifndef TR_MODEL_TESSELLATION_H
#define TR_MODEL_TESSELLATION_H

#include <math.h>

#define MODEL_TESSELLATION_LOW 0
#define MODEL_TESSELLATION_MEDIUM 1
#define MODEL_TESSELLATION_HIGH 2

#define MODEL_TESSELLATION_MAX_FACTOR 3
#define MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES 10
#define MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES 27

typedef struct modelTessellationVertex_s {
	float xyz[3];
	float normal[3];
	float texCoords[2];
	unsigned char color[4];
} modelTessellationVertex_t;

static ID_INLINE int R_ModelTessellationFactor( int quality ) {
	if ( quality < MODEL_TESSELLATION_LOW ) {
		quality = MODEL_TESSELLATION_LOW;
	} else if ( quality > MODEL_TESSELLATION_HIGH ) {
		quality = MODEL_TESSELLATION_HIGH;
	}

	return quality + 1;
}

static ID_INLINE int R_ModelTessellationTriangleVertexCount( int factor ) {
	return ( factor + 1 ) * ( factor + 2 ) / 2;
}

static ID_INLINE int R_ModelTessellationTriangleIndexCount( int factor ) {
	return factor * factor * 3;
}

static ID_INLINE void R_ModelTessellationNormalize( float normal[3], const float fallback[3] ) {
	float length = sqrtf( normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2] );

	if ( length > 0.000001f ) {
		float inverseLength = 1.0f / length;
		normal[0] *= inverseLength;
		normal[1] *= inverseLength;
		normal[2] *= inverseLength;
	} else {
		normal[0] = fallback[0];
		normal[1] = fallback[1];
		normal[2] = fallback[2];
	}
}

/*
 * Evaluate a small Phong-tessellated triangle entirely on the CPU. The
 * position is projected onto the three vertex tangent planes and blended by
 * barycentric weight, so original vertices remain fixed while silhouettes
 * and coarse animated contours become curved. Shared edges evaluate from the
 * same endpoint data, which keeps indexed model surfaces watertight. Input
 * normals are expected to be normalized by the model-surface wrapper.
 */
static ID_INLINE void R_ModelTessellateTriangle(
	const modelTessellationVertex_t input[3],
	int factor,
	modelTessellationVertex_t output[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES],
	unsigned int indexes[MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES] ) {
	modelTessellationVertex_t control[3];
	float edge1[3], edge2[3], faceNormal[3];
	unsigned int grid[MODEL_TESSELLATION_MAX_FACTOR + 1][MODEL_TESSELLATION_MAX_FACTOR + 1];
	int i, j, k, vertexCount, indexCount;

	if ( factor < 1 ) {
		factor = 1;
	} else if ( factor > MODEL_TESSELLATION_MAX_FACTOR ) {
		factor = MODEL_TESSELLATION_MAX_FACTOR;
	}

	for ( k = 0; k < 3; k++ ) {
		edge1[k] = input[1].xyz[k] - input[0].xyz[k];
		edge2[k] = input[2].xyz[k] - input[0].xyz[k];
	}
	faceNormal[0] = edge1[1] * edge2[2] - edge1[2] * edge2[1];
	faceNormal[1] = edge1[2] * edge2[0] - edge1[0] * edge2[2];
	faceNormal[2] = edge1[0] * edge2[1] - edge1[1] * edge2[0];
	{
		static const float defaultNormal[3] = { 0.0f, 0.0f, 1.0f };
		R_ModelTessellationNormalize( faceNormal, defaultNormal );
	}

	for ( i = 0; i < 3; i++ ) {
		control[i] = input[i];
	}

	vertexCount = 0;
	for ( i = 0; i <= factor; i++ ) {
		for ( j = 0; j <= factor - i; j++ ) {
			float barycentric[3];
			float linear[3];
			float phong[3];
			modelTessellationVertex_t *vertex = &output[vertexCount];

			barycentric[1] = (float)i / (float)factor;
			barycentric[2] = (float)j / (float)factor;
			barycentric[0] = 1.0f - barycentric[1] - barycentric[2];

			for ( k = 0; k < 3; k++ ) {
				linear[k] = barycentric[0] * control[0].xyz[k] +
					barycentric[1] * control[1].xyz[k] +
					barycentric[2] * control[2].xyz[k];
				phong[k] = 0.0f;
				vertex->normal[k] = barycentric[0] * control[0].normal[k] +
					barycentric[1] * control[1].normal[k] +
					barycentric[2] * control[2].normal[k];
			}

			for ( k = 0; k < 3; k++ ) {
				float delta[3];
				float distance;
				int axis;

				for ( axis = 0; axis < 3; axis++ ) {
					delta[axis] = linear[axis] - control[k].xyz[axis];
				}
				distance = delta[0] * control[k].normal[0] +
					delta[1] * control[k].normal[1] +
					delta[2] * control[k].normal[2];
				for ( axis = 0; axis < 3; axis++ ) {
					phong[axis] += barycentric[k] *
						( linear[axis] - distance * control[k].normal[axis] );
				}
			}

			for ( k = 0; k < 3; k++ ) {
				vertex->xyz[k] = phong[k];
			}
			R_ModelTessellationNormalize( vertex->normal, faceNormal );

			for ( k = 0; k < 2; k++ ) {
				vertex->texCoords[k] = barycentric[0] * control[0].texCoords[k] +
					barycentric[1] * control[1].texCoords[k] +
					barycentric[2] * control[2].texCoords[k];
			}
			for ( k = 0; k < 4; k++ ) {
				float color = barycentric[0] * control[0].color[k] +
					barycentric[1] * control[1].color[k] +
					barycentric[2] * control[2].color[k];
				vertex->color[k] = (unsigned char)( color + 0.5f );
			}

			grid[i][j] = (unsigned int)vertexCount++;
		}
	}

	indexCount = 0;
	for ( i = 0; i < factor; i++ ) {
		for ( j = 0; j < factor - i; j++ ) {
			indexes[indexCount++] = grid[i][j];
			indexes[indexCount++] = grid[i + 1][j];
			indexes[indexCount++] = grid[i][j + 1];

			if ( j < factor - i - 1 ) {
				indexes[indexCount++] = grid[i + 1][j];
				indexes[indexCount++] = grid[i + 1][j + 1];
				indexes[indexCount++] = grid[i][j + 1];
			}
		}
	}
}

#endif
