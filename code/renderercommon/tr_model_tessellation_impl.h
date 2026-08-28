#ifndef TR_MODEL_TESSELLATION_IMPL_H
#define TR_MODEL_TESSELLATION_IMPL_H

#define RB_MODEL_TESSELLATION_EDGE_HASH_SIZE 2048

typedef enum {
	RB_MODEL_TESSELLATION_KEY_INTERIOR,
	RB_MODEL_TESSELLATION_KEY_VERTEX,
	RB_MODEL_TESSELLATION_KEY_EDGE
} rbModelTessellationKeyType_t;

typedef struct {
	rbModelTessellationKeyType_t type;
	glIndex_t source[2];
	int step;
} rbModelTessellationKey_t;

typedef struct {
	glIndex_t source[2];
	int output[MODEL_TESSELLATION_MAX_FACTOR - 1];
	unsigned int generation;
} rbModelTessellationEdge_t;

static modelTessellationVertex_t rb_modelTessellationSourceVertexes[SHADER_MAX_VERTEXES];
static glIndex_t rb_modelTessellationSourceIndexes[SHADER_MAX_INDEXES];
static int rb_modelTessellationVertexOutput[SHADER_MAX_VERTEXES];
static rbModelTessellationEdge_t rb_modelTessellationEdges[RB_MODEL_TESSELLATION_EDGE_HASH_SIZE];
static unsigned int rb_modelTessellationGeneration = 1;
static const float rb_modelTessellationDefaultNormal[3] = { 0.0f, 0.0f, 1.0f };

static ID_INLINE void RB_ModelTessellationResetCache( int numSourceVertexes ) {
	int i;

	for ( i = 0; i < numSourceVertexes; i++ ) {
		rb_modelTessellationVertexOutput[i] = -1;
	}
	if ( ++rb_modelTessellationGeneration == 0 ) {
		Com_Memset( rb_modelTessellationEdges, 0, sizeof( rb_modelTessellationEdges ) );
		rb_modelTessellationGeneration = 1;
	}
}

static ID_INLINE rbModelTessellationEdge_t *RB_ModelTessellationFindEdge(
	glIndex_t source0, glIndex_t source1, qboolean create ) {
	unsigned int slot = ( source0 * 73856093u ^ source1 * 19349663u ) &
		( RB_MODEL_TESSELLATION_EDGE_HASH_SIZE - 1 );
	unsigned int probe;

	for ( probe = 0; probe < RB_MODEL_TESSELLATION_EDGE_HASH_SIZE; probe++ ) {
		rbModelTessellationEdge_t *edge = &rb_modelTessellationEdges[slot];

		if ( edge->generation != rb_modelTessellationGeneration ) {
			int i;
			if ( !create ) {
				return NULL;
			}
			edge->generation = rb_modelTessellationGeneration;
			edge->source[0] = source0;
			edge->source[1] = source1;
			for ( i = 0; i < MODEL_TESSELLATION_MAX_FACTOR - 1; i++ ) {
				edge->output[i] = -1;
			}
			return edge;
		}
		if ( edge->source[0] == source0 && edge->source[1] == source1 ) {
			return edge;
		}
		slot = ( slot + 1 ) & ( RB_MODEL_TESSELLATION_EDGE_HASH_SIZE - 1 );
	}

	return NULL;
}

static ID_INLINE rbModelTessellationKey_t RB_ModelTessellationKey(
	const glIndex_t source[3], const int weight[3], int factor ) {
	rbModelTessellationKey_t key;
	int nonzero[2];
	int nonzeroCount = 0;
	int i;

	key.type = RB_MODEL_TESSELLATION_KEY_INTERIOR;
	key.source[0] = key.source[1] = 0;
	key.step = 0;

	for ( i = 0; i < 3; i++ ) {
		if ( weight[i] == factor ) {
			key.type = RB_MODEL_TESSELLATION_KEY_VERTEX;
			key.source[0] = source[i];
			return key;
		}
		if ( weight[i] > 0 && nonzeroCount < 2 ) {
			nonzero[nonzeroCount++] = i;
		}
	}

	if ( nonzeroCount == 2 && source[nonzero[0]] != source[nonzero[1]] ) {
		int low = nonzero[0];
		int high = nonzero[1];
		if ( source[low] > source[high] ) {
			int swap = low;
			low = high;
			high = swap;
		}
		key.type = RB_MODEL_TESSELLATION_KEY_EDGE;
		key.source[0] = source[low];
		key.source[1] = source[high];
		key.step = weight[high] - 1;
	}

	return key;
}

static ID_INLINE int RB_ModelTessellationCachedOutput(
	const rbModelTessellationKey_t *key, qboolean create ) {
	if ( key->type == RB_MODEL_TESSELLATION_KEY_VERTEX ) {
		return rb_modelTessellationVertexOutput[key->source[0]];
	}
	if ( key->type == RB_MODEL_TESSELLATION_KEY_EDGE ) {
		rbModelTessellationEdge_t *edge = RB_ModelTessellationFindEdge(
			key->source[0], key->source[1], create );
		if ( edge && key->step >= 0 &&
			key->step < MODEL_TESSELLATION_MAX_FACTOR - 1 ) {
			return edge->output[key->step];
		}
	}
	return -1;
}

static ID_INLINE void RB_ModelTessellationStoreOutput(
	const rbModelTessellationKey_t *key, int output ) {
	if ( key->type == RB_MODEL_TESSELLATION_KEY_VERTEX ) {
		rb_modelTessellationVertexOutput[key->source[0]] = output;
	} else if ( key->type == RB_MODEL_TESSELLATION_KEY_EDGE ) {
		rbModelTessellationEdge_t *edge = RB_ModelTessellationFindEdge(
			key->source[0], key->source[1], qtrue );
		if ( edge && key->step >= 0 &&
			key->step < MODEL_TESSELLATION_MAX_FACTOR - 1 ) {
			edge->output[key->step] = output;
		}
	}
}

static ID_INLINE int RB_ModelTessellationAppendVertex(
	const modelTessellationVertex_t *vertex ) {
	int output = tess.numVertexes++;
	int component;

	for ( component = 0; component < 3; component++ ) {
		tess.xyz[output][component] = vertex->xyz[component];
		tess.normal[output][component] = vertex->normal[component];
	}
	tess.xyz[output][3] = 1.0f;
	tess.normal[output][3] = 0.0f;
	for ( component = 0; component < 2; component++ ) {
		tess.texCoords[0][output][component] = vertex->texCoords[component];
	}
	for ( component = 0; component < 4; component++ ) {
		tess.vertexColors[output].rgba[component] = vertex->color[component];
	}

	return output;
}

void RB_TessellateModelSurface( int firstVertex, int numVertexes,
	int firstIndex, int numIndexes, surfaceType_t surfType,
	qboolean hasVertexColors ) {
	modelTessellationVertex_t generatedVertexes[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES];
	unsigned int generatedIndexes[MODEL_TESSELLATION_MAX_TRIANGLE_INDEXES];
	int factor;
	int generatedIndexCount;
	int i, triangle;

	/* Stencil shadow volumes require shared source indexes for silhouette edge
	 * pairing. Keep that compatibility-sensitive pass on the authored mesh. */
	if ( !r_modelTessellation || tess.shader == tr.shadowShader ) {
		return;
	}

	factor = R_ModelTessellationFactor( r_modelTessellation->integer );
	if ( factor <= 1 || numVertexes <= 0 || numIndexes < 3 ) {
		return;
	}
	if ( firstVertex < 0 || firstIndex < 0 ||
		firstVertex + numVertexes > tess.numVertexes ||
		firstIndex + numIndexes > tess.numIndexes ||
		numVertexes > SHADER_MAX_VERTEXES || numIndexes > SHADER_MAX_INDEXES ) {
		return;
	}

	for ( i = 0; i < numVertexes; i++ ) {
		const int source = firstVertex + i;
		int component;

		for ( component = 0; component < 3; component++ ) {
			rb_modelTessellationSourceVertexes[i].xyz[component] = tess.xyz[source][component];
			rb_modelTessellationSourceVertexes[i].normal[component] = tess.normal[source][component];
		}
		R_ModelTessellationNormalize( rb_modelTessellationSourceVertexes[i].normal,
			rb_modelTessellationDefaultNormal );
		for ( component = 0; component < 2; component++ ) {
			rb_modelTessellationSourceVertexes[i].texCoords[component] = tess.texCoords[0][source][component];
		}
		for ( component = 0; component < 4; component++ ) {
			rb_modelTessellationSourceVertexes[i].color[component] = hasVertexColors ?
				tess.vertexColors[source].rgba[component] : 255;
		}
	}

	for ( i = 0; i < numIndexes; i++ ) {
		const glIndex_t sourceIndex = tess.indexes[firstIndex + i];
		if ( sourceIndex < (glIndex_t)firstVertex ||
			sourceIndex >= (glIndex_t)( firstVertex + numVertexes ) ) {
			return;
		}
		rb_modelTessellationSourceIndexes[i] = sourceIndex - firstVertex;
	}

	tess.numVertexes = firstVertex;
	tess.numIndexes = firstIndex;
	generatedIndexCount = R_ModelTessellationTriangleIndexCount( factor );
	RB_ModelTessellationResetCache( numVertexes );

	for ( triangle = 0; triangle + 2 < numIndexes; triangle += 3 ) {
		modelTessellationVertex_t input[3];
		rbModelTessellationKey_t keys[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES];
		int resolved[MODEL_TESSELLATION_MAX_TRIANGLE_VERTICES];
		glIndex_t source[3];
		int missingVertexes = 0;
		int vertex = 0;
		int row, column, index;

		for ( i = 0; i < 3; i++ ) {
			source[i] = rb_modelTessellationSourceIndexes[triangle + i];
			input[i] = rb_modelTessellationSourceVertexes[source[i]];
		}
		R_ModelTessellateTriangle( input, factor, generatedVertexes, generatedIndexes );

		for ( row = 0; row <= factor; row++ ) {
			for ( column = 0; column <= factor - row; column++ ) {
				int weight[3];
				weight[1] = row;
				weight[2] = column;
				weight[0] = factor - row - column;
				keys[vertex] = RB_ModelTessellationKey( source, weight, factor );
				if ( RB_ModelTessellationCachedOutput( &keys[vertex], qfalse ) < 0 ) {
					missingVertexes++;
				}
				vertex++;
			}
		}

		if ( tess.numVertexes + missingVertexes >= SHADER_MAX_VERTEXES ||
			tess.numIndexes + generatedIndexCount >= SHADER_MAX_INDEXES ) {
			RB_CHECKOVERFLOW( missingVertexes, generatedIndexCount );
			RB_ModelTessellationResetCache( numVertexes );
		}
		tess.surfType = surfType;

		for ( vertex = 0; vertex < R_ModelTessellationTriangleVertexCount( factor ); vertex++ ) {
			resolved[vertex] = RB_ModelTessellationCachedOutput( &keys[vertex], qtrue );
			if ( resolved[vertex] < 0 ) {
				resolved[vertex] = RB_ModelTessellationAppendVertex( &generatedVertexes[vertex] );
				RB_ModelTessellationStoreOutput( &keys[vertex], resolved[vertex] );
			}
		}
		for ( index = 0; index < generatedIndexCount; index++ ) {
			tess.indexes[tess.numIndexes++] = resolved[generatedIndexes[index]];
		}
	}
}

#endif
