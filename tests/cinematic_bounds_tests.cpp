#include "../code/client/cinematic_bounds.hpp"

#include <cstdint>
#include <cstdio>

namespace {

int failures;

void Check( bool condition, const char *message )
{
	if ( !condition ) {
		std::fprintf( stderr, "FAIL: %s\n", message );
		++failures;
	}
}

void TestRoQReadBounds()
{
	using namespace fnq3::client;
	constexpr auto tooLarge = static_cast<std::uint32_t>( kRoQMaxPayloadBytes + 1 );
	constexpr std::int64_t filePosition = 1024;
	constexpr std::uint32_t payloadBytes = 13586;
	constexpr auto terminal = RoQPlanRead( payloadBytes, filePosition,
		filePosition + payloadBytes );
	constexpr auto continued = RoQPlanRead( payloadBytes, filePosition,
		filePosition + payloadBytes + kRoQChunkHeaderBytes );

	Check( kRoQReadBufferBytes == 65544,
		"read buffer includes the eight-byte next-chunk header" );
	Check( RoQPayloadFits( 0 ) && RoQPayloadFits( 65536 ),
		"historical payload range remains accepted" );
	Check( !RoQInitialPayloadIsValid( 0 )
		&& RoQInitialPayloadIsValid( 65536 ),
		"the first chunk requires a non-empty bounded payload" );
	Check( !RoQPayloadFits( tooLarge ),
		"payloads beyond the historical limit are rejected" );
	Check( terminal.kind == RoQReadKind::terminalPayload
		&& terminal.bytes == payloadBytes
		&& RoQReadComplete( terminal, payloadBytes ),
		"a final retail-style payload is accepted without lookahead" );
	Check( continued.kind == RoQReadKind::payloadAndNextHeader
		&& continued.bytes == payloadBytes + kRoQChunkHeaderBytes
		&& RoQReadComplete( continued,
			payloadBytes + static_cast<int>( kRoQChunkHeaderBytes ) ),
		"a non-terminal payload includes the complete next header" );
	Check( !RoQReadComplete( terminal, payloadBytes - 1 )
		&& !RoQReadComplete( continued,
			payloadBytes + static_cast<int>( kRoQChunkHeaderBytes ) - 1 )
		&& !RoQReadComplete( continued, -1 ),
		"short and failed reads remain rejected for both read kinds" );
	for ( std::int64_t trailingBytes = 1;
		trailingBytes < static_cast<std::int64_t>( kRoQChunkHeaderBytes );
		++trailingBytes ) {
		Check( !RoQReadPlanIsValid( RoQPlanRead( payloadBytes, filePosition,
			filePosition + payloadBytes + trailingBytes ) ),
			"partial trailing chunk headers are rejected" );
	}
	Check( !RoQReadPlanIsValid( RoQPlanRead( payloadBytes, -1,
		filePosition + payloadBytes ) )
		&& !RoQReadPlanIsValid( RoQPlanRead( payloadBytes, filePosition,
			filePosition + payloadBytes - 1 ) )
		&& !RoQReadPlanIsValid( RoQPlanRead( tooLarge, filePosition,
			filePosition + tooLarge ) ),
		"invalid positions, truncated payloads, and oversized payloads are rejected" );
	constexpr auto maxTerminal = RoQPlanRead( 65536, filePosition,
		filePosition + 65536 );
	constexpr auto maxContinued = RoQPlanRead( 65536, filePosition,
		filePosition + 65536 + kRoQChunkHeaderBytes );
	Check( maxTerminal.bytes == kRoQMaxPayloadBytes
		&& maxContinued.bytes == kRoQReadBufferBytes,
		"maximum payload reads stay within the bounded buffer" );
	Check( RoQFileHeaderReadComplete( 16 )
		&& !RoQFileHeaderReadComplete( 15 )
		&& !RoQFileHeaderReadComplete( -1 ),
		"bootstrap reads require the complete file and first-chunk headers" );
	Check( RoQRangeFits( 65536, 8, 65544 )
		&& !RoQRangeFits( 65537, 8, 65544 )
		&& !RoQRangeFits( 65544, 1, 65544 ),
		"payload and header ranges remain inside their active boundary" );
}

void TestRoQAudioBounds()
{
	using namespace fnq3::client;

	Check( kRoQDecodedAudioSampleCapacity == 131072,
		"mono-to-stereo output has two samples per input byte" );
	Check( RoQStereoPayloadIsPaired( 0 )
		&& RoQStereoPayloadIsPaired( 65536 ),
		"complete stereo byte pairs are accepted" );
	Check( !RoQStereoPayloadIsPaired( 1 )
		&& !RoQStereoPayloadIsPaired( 65535 ),
		"incomplete stereo byte pairs are rejected" );
}

void TestRoQGeometryBounds()
{
	using namespace fnq3::client;

	Check( RoQQuadInfoIsValid( 8, 512, 512 )
		&& RoQQuadInfoIsValid( 8, 512, 256 )
		&& RoQQuadInfoIsValid( 8, 1, 1 ),
		"bounded non-empty cinematic dimensions are accepted" );
	Check( !RoQQuadInfoIsValid( 0, 512, 256 )
		&& !RoQQuadInfoIsValid( 7, 512, 256 )
		&& !RoQQuadInfoIsValid( 9, 512, 256 ),
		"quad-info chunks require exactly eight payload bytes" );
	Check( !RoQQuadInfoIsValid( 8, 0, 256 )
		&& !RoQQuadInfoIsValid( 8, 512, 0 )
		&& !RoQQuadInfoIsValid( 8, 513, 256 )
		&& !RoQQuadInfoIsValid( 8, 512, 513 ),
		"empty or oversized cinematic dimensions are rejected" );
}

void TestRoQDecoderInputBounds()
{
	using namespace fnq3::client;

	constexpr auto retailShortCodebook = RoQPlanCodebook( 1536, 0 );
	constexpr auto retailFullCodebook = RoQPlanCodebook( 2560, 0 );
	constexpr auto partialCodebook = RoQPlanCodebook( 1537, 0 );
	Check( retailShortCodebook.valid
		&& retailShortCodebook.twoByTwoEntries == 256
		&& retailShortCodebook.fourByFourEntries == 0,
		"retail zero-flag codebooks may contain only 2x2 entries" );
	Check( retailFullCodebook.valid
		&& retailFullCodebook.twoByTwoEntries == 256
		&& retailFullCodebook.fourByFourEntries == 256,
		"full zero-flag codebooks retain all 2x2 and 4x4 entries" );
	Check( !partialCodebook.valid && partialCodebook.requiredBytes == 2560,
		"truncated implicit 4x4 codebooks are rejected" );
	constexpr auto flaggedCodebook = RoQPlanCodebook( 6 * 3 + 4 * 2, 0x0302 );
	Check( flaggedCodebook.valid
		&& flaggedCodebook.twoByTwoEntries == 3
		&& flaggedCodebook.fourByFourEntries == 2,
		"explicit codebook entry counts produce an exact input bound" );
	Check( !RoQPlanCodebook( flaggedCodebook.requiredBytes - 1, 0x0302 ).valid,
		"short explicit codebooks are rejected" );
	constexpr auto paddedCodebook = RoQPlanCodebook( 6 * 3 + 1, 0x0300 );
	Check( paddedCodebook.valid
		&& paddedCodebook.twoByTwoEntries == 3
		&& paddedCodebook.fourByFourEntries == 0
		&& paddedCodebook.requiredBytes == 18,
		"nonzero flags preserve an explicit zero 4x4 count with padding" );
	constexpr auto implicitFullCodebook = RoQPlanCodebook( 6 * 3 + 4 * 256, 0x0300 );
	Check( implicitFullCodebook.valid
		&& implicitFullCodebook.twoByTwoEntries == 3
		&& implicitFullCodebook.fourByFourEntries == 256
		&& implicitFullCodebook.requiredBytes == 1042,
		"a full implicit 4x4 table remains compatible with FFmpeg-style RoQ files" );

	const std::uint8_t encoded[] = { 0x34, 0x12, 0xab };
	RoQByteReader reader( encoded, sizeof( encoded ) );
	std::uint16_t word = 0;
	std::uint8_t value = 0;
	Check( reader.ReadLittleShort( word ) && word == 0x1234
		&& reader.ReadByte( value ) && value == 0xab
		&& reader.remaining() == 0,
		"bounded VQ input reads decode complete values" );
	Check( !reader.ReadByte( value ) && !reader.ReadLittleShort( word ),
		"bounded VQ input reads fail at the declared payload end" );

	Check( RoQBlockFits( 0, 32, 8, 2048, 16384 )
		&& RoQBlockFits( 14304, 32, 8, 2048, 28672 ),
		"complete motion blocks inside the frame buffer are accepted" );
	Check( !RoQBlockFits( -1, 32, 8, 2048, 16384 )
		&& !RoQBlockFits( 14305, 32, 8, 2048, 28672 )
		&& !RoQBlockFits( 0, 32, 0, 2048, 16384 ),
		"negative, overflowing, and empty motion blocks are rejected" );
}

} // namespace

int main()
{
	TestRoQReadBounds();
	TestRoQAudioBounds();
	TestRoQGeometryBounds();
	TestRoQDecoderInputBounds();
	return failures == 0 ? 0 : 1;
}
