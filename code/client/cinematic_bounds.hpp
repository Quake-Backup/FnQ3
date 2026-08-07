#pragma once

#include <cstddef>
#include <cstdint>

namespace fnq3::client {

inline constexpr std::size_t kRoQFileHeaderBytes = 16;
inline constexpr std::size_t kRoQChunkHeaderBytes = 8;
inline constexpr std::size_t kRoQMaxPayloadBytes = 65536;
inline constexpr std::size_t kRoQReadBufferBytes =
	kRoQMaxPayloadBytes + kRoQChunkHeaderBytes;
inline constexpr std::size_t kRoQDecodedAudioSampleCapacity =
	kRoQMaxPayloadBytes * 2;
inline constexpr std::uint32_t kRoQQuadInfoBytes = 8;
inline constexpr std::uint32_t kRoQMaxWidth = 512;
inline constexpr std::uint32_t kRoQMaxHeight = 512;
inline constexpr std::uint64_t kRoQStatusCapacity = 32768;
inline constexpr std::uint64_t kRoQStatusSentinelCount = 64;

enum class RoQReadKind {
	invalid,
	terminalPayload,
	payloadAndNextHeader,
};

struct RoQReadPlan {
	RoQReadKind kind;
	std::size_t bytes;
};

struct RoQCodebookPlan {
	bool valid;
	std::uint16_t twoByTwoEntries;
	std::uint16_t fourByFourEntries;
	std::size_t requiredBytes;
};

class RoQByteReader {
public:
	RoQByteReader( const std::uint8_t *data, std::size_t bytes ) noexcept
		: cursor_( data ), remaining_( bytes )
	{
	}

	bool ReadByte( std::uint8_t &value ) noexcept
	{
		if ( remaining_ < 1 ) {
			return false;
		}
		value = *cursor_++;
		--remaining_;
		return true;
	}

	bool ReadLittleShort( std::uint16_t &value ) noexcept
	{
		if ( remaining_ < 2 ) {
			return false;
		}
		value = static_cast<std::uint16_t>( cursor_[0] )
			| static_cast<std::uint16_t>( cursor_[1] ) << 8;
		cursor_ += 2;
		remaining_ -= 2;
		return true;
	}

	std::size_t remaining() const noexcept
	{
		return remaining_;
	}

private:
	const std::uint8_t *cursor_;
	std::size_t remaining_;
};

constexpr bool RoQPayloadFits( std::uint32_t payloadBytes ) noexcept
{
	return payloadBytes <= kRoQMaxPayloadBytes;
}

constexpr bool RoQInitialPayloadIsValid( std::uint32_t payloadBytes ) noexcept
{
	return payloadBytes > 0 && RoQPayloadFits( payloadBytes );
}

constexpr bool RoQQuadInfoIsValid( std::uint32_t payloadBytes,
	std::uint32_t width, std::uint32_t height ) noexcept
{
	if ( payloadBytes != kRoQQuadInfoBytes || width == 0 || height == 0
		|| width > kRoQMaxWidth || height > kRoQMaxHeight ) {
		return false;
	}

	const std::uint64_t pixels = static_cast<std::uint64_t>( width ) * height;
	const std::uint64_t baseQuadCells = pixels / 16;
	const std::uint64_t requiredStatusEntries = baseQuadCells
		+ baseQuadCells / 4 + kRoQStatusSentinelCount;
	return requiredStatusEntries <= kRoQStatusCapacity;
}

constexpr RoQCodebookPlan RoQPlanCodebook( std::uint32_t payloadBytes,
	std::uint16_t flags ) noexcept
{
	if ( !RoQPayloadFits( payloadBytes ) ) {
		return { false, 0, 0, 0 };
	}

	std::uint16_t twoByTwoEntries = flags >> 8;
	if ( twoByTwoEntries == 0 ) {
		twoByTwoEntries = 256;
	}
	std::uint16_t fourByFourEntries = flags & 0xff;
	const std::size_t twoByTwoBytes =
		static_cast<std::size_t>( twoByTwoEntries ) * 6;
	const std::size_t fullFourByFourBytes = 256 * 4;
	if ( fourByFourEntries == 0 && twoByTwoBytes < payloadBytes
		&& ( flags == 0
			|| payloadBytes - twoByTwoBytes >= fullFourByFourBytes ) ) {
		fourByFourEntries = 256;
	}
	const std::size_t requiredBytes = twoByTwoBytes
		+ static_cast<std::size_t>( fourByFourEntries ) * 4;
	return { requiredBytes <= payloadBytes, twoByTwoEntries,
		fourByFourEntries, requiredBytes };
}

constexpr bool RoQBlockFits( std::int64_t offset, std::size_t rowBytes,
	std::size_t rows, std::size_t stride, std::size_t capacity ) noexcept
{
	if ( offset < 0 || rowBytes == 0 || rows == 0 ) {
		return false;
	}
	const auto start = static_cast<std::uint64_t>( offset );
	const auto lastRow = static_cast<std::uint64_t>( rows - 1 ) * stride;
	return start <= capacity && lastRow <= capacity - start
		&& rowBytes <= capacity - start - lastRow;
}

constexpr RoQReadPlan RoQPlanRead( std::uint32_t payloadBytes,
	std::int64_t filePosition, std::int64_t fileSize ) noexcept
{
	if ( !RoQPayloadFits( payloadBytes ) || filePosition < 0
		|| fileSize < filePosition ) {
		return { RoQReadKind::invalid, 0 };
	}

	const auto remainingBytes = static_cast<std::uint64_t>(
		fileSize - filePosition );
	if ( remainingBytes == payloadBytes ) {
		return { RoQReadKind::terminalPayload,
			static_cast<std::size_t>( payloadBytes ) };
	}
	if ( remainingBytes >= payloadBytes + kRoQChunkHeaderBytes ) {
		return { RoQReadKind::payloadAndNextHeader,
			static_cast<std::size_t>( payloadBytes ) + kRoQChunkHeaderBytes };
	}
	return { RoQReadKind::invalid, 0 };
}

constexpr bool RoQReadPlanIsValid( RoQReadPlan plan ) noexcept
{
	return plan.kind != RoQReadKind::invalid;
}

constexpr bool RoQReadComplete( RoQReadPlan plan, int bytesRead ) noexcept
{
	return RoQReadPlanIsValid( plan ) && bytesRead >= 0
		&& static_cast<std::size_t>( bytesRead ) == plan.bytes;
}

constexpr bool RoQFileHeaderReadComplete( int bytesRead ) noexcept
{
	return bytesRead == static_cast<int>( kRoQFileHeaderBytes );
}

constexpr bool RoQRangeFits( std::size_t offset, std::size_t bytes,
	std::size_t limit ) noexcept
{
	return offset <= limit && bytes <= limit - offset;
}

constexpr bool RoQStereoPayloadIsPaired( std::uint32_t payloadBytes ) noexcept
{
	return RoQPayloadFits( payloadBytes ) && ( payloadBytes & 1u ) == 0;
}

} // namespace fnq3::client
