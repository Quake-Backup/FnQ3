#include <cassert>
#include <cmath>
#include <cstring>

#define ID_INLINE inline
#include "../code/renderercommon/tr_model_tessellation.h"

static bool Near( float lhs, float rhs, float epsilon = 0.0001f ) {
	return std::fabs( lhs - rhs ) <= epsilon;
}

static modelTessellationVertex_t Vertex( float x, float y, float z,
	float nx, float ny, float nz, float s, float t,
	unsigned char red, unsigned char green, unsigned char blue ) {
	modelTessellationVertex_t vertex = {};
	vertex.xyz[0] = x;
	vertex.xyz[1] = y;
	vertex.xyz[2] = z;
	vertex.normal[0] = nx;
	vertex.normal[1] = ny;
	vertex.normal[2] = nz;
	vertex.texCoords[0] = s;
	vertex.texCoords[1] = t;
	vertex.color[0] = red;
	vertex.color[1] = green;
	vertex.color[2] = blue;
	vertex.color[3] = 255;
	return vertex;
}

static void TestQualityLevels() {
	assert( R_ModelTessellationFactor( -5 ) == 1 );
	assert( R_ModelTessellationFactor( MODEL_TESSELLATION_LOW ) == 1 );
	assert( R_ModelTessellationFactor( MODEL_TESSELLATION_MEDIUM ) == 2 );
	assert( R_ModelTessellationFactor( MODEL_TESSELLATION_HIGH ) == 3 );
	assert( R_ModelTessellationFactor( 99 ) == 3 );

	assert( R_ModelTessellationTriangleVertexCount( 1 ) == 3 );
	assert( R_ModelTessellationTriangleVertexCount( 2 ) == 6 );
	assert( R_ModelTessellationTriangleVertexCount( 3 ) == 10 );
	assert( R_ModelTessellationTriangleIndexCount( 1 ) == 3 );
	assert( R_ModelTessellationTriangleIndexCount( 2 ) == 12 );
	assert( R_ModelTessellationTriangleIndexCount( 3 ) == 27 );
}

static void TestFlatTriangleStaysFlat() {
	modelTessellationVertex_t input[3] = {
		Vertex( 0, 0, 0, 0, 0, 1, 0, 0, 255, 0, 0 ),
		Vertex( 1, 0, 0, 0, 0, 1, 1, 0, 0, 255, 0 ),
		Vertex( 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 255 )
	};
	modelTessellationVertex_t output[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES] = {};
	unsigned int indexes[MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES] = {};

	R_ModelTessellateTriangle( input, 3, output, indexes );
	for ( int i = 0; i < R_ModelTessellationTriangleVertexCount( 3 ); ++i ) {
		assert( Near( output[i].xyz[2], 0.0f ) );
		assert( Near( output[i].normal[0], 0.0f ) );
		assert( Near( output[i].normal[1], 0.0f ) );
		assert( Near( output[i].normal[2], 1.0f ) );
	}
	for ( int i = 0; i < R_ModelTessellationTriangleIndexCount( 3 ); ++i ) {
		assert( indexes[i] < 10 );
	}
}

static void TestCurvedTrianglePreservesCornersAndBulgesEdges() {
	modelTessellationVertex_t input[3] = {
		Vertex( 1, 0, 0, 1, 0, 0, 0, 0, 255, 0, 0 ),
		Vertex( 0, 1, 0, 0, 1, 0, 1, 0, 0, 255, 0 ),
		Vertex( 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 255 )
	};
	modelTessellationVertex_t output[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES] = {};
	unsigned int indexes[MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES] = {};

	R_ModelTessellateTriangle( input, 2, output, indexes );

	// Row order is p0, p0-p2 midpoint, p2, p0-p1 midpoint, p1-p2 midpoint, p1.
	assert( Near( output[0].xyz[0], 1.0f ) && Near( output[0].xyz[1], 0.0f ) );
	assert( Near( output[2].xyz[2], 1.0f ) );
	assert( Near( output[5].xyz[1], 1.0f ) );
	assert( output[3].xyz[0] > 0.5f );
	assert( output[3].xyz[1] > 0.5f );
	assert( Near( output[3].xyz[2], 0.0f ) );
	assert( Near( output[3].texCoords[0], 0.5f ) );
	assert( output[3].color[0] == 128 );
	assert( output[3].color[1] == 128 );
	assert( output[3].color[2] == 0 );

	for ( int i = 0; i < R_ModelTessellationTriangleVertexCount( 2 ); ++i ) {
		const float normalLength = std::sqrt(
			output[i].normal[0] * output[i].normal[0] +
			output[i].normal[1] * output[i].normal[1] +
			output[i].normal[2] * output[i].normal[2] );
		assert( Near( normalLength, 1.0f ) );
	}
}

static void TestSharedEdgesStayWatertight() {
	modelTessellationVertex_t first[3] = {
		Vertex( 1, 0, 0, 1, 0, 0, 0, 0, 255, 255, 255 ),
		Vertex( 0, 1, 0, 0, 1, 0, 1, 0, 255, 255, 255 ),
		Vertex( 0, 0, 1, 0, 0, 1, 0, 1, 255, 255, 255 )
	};
	modelTessellationVertex_t second[3] = {
		first[1],
		first[0],
		Vertex( 0, 0, -1, 0, 0, -1, 0, -1, 255, 255, 255 )
	};
	modelTessellationVertex_t firstOutput[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES] = {};
	modelTessellationVertex_t secondOutput[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES] = {};
	unsigned int indexes[MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES] = {};
	const int edgeRows[4] = { 0, 4, 7, 9 };

	R_ModelTessellateTriangle( first, 3, firstOutput, indexes );
	R_ModelTessellateTriangle( second, 3, secondOutput, indexes );
	for ( int i = 0; i < 4; ++i ) {
		for ( int axis = 0; axis < 3; ++axis ) {
			assert( Near( firstOutput[edgeRows[i]].xyz[axis],
				secondOutput[edgeRows[3 - i]].xyz[axis] ) );
		}
	}
}

int main() {
	TestQualityLevels();
	TestFlatTriangleStaysFlat();
	TestCurvedTrianglePreservesCornersAndBulgesEdges();
	TestSharedEdgesStayWatertight();
	return 0;
}
