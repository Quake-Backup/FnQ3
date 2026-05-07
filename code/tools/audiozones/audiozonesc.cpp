/*
===========================================================================
Copyright (C) 2026

This file is part of FnQuake3.

FnQuake3 is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
===========================================================================
*/

#include "../../audio/AudioZoneFormat.h"

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

namespace azfmt = fnq3_audiozones;

namespace {

struct Vec3 {
	float x = 0.0f;
	float y = 0.0f;
	float z = 0.0f;
};

struct Zone {
	std::string name;
	Vec3 mins;
	Vec3 maxs;
	bool haveMins = false;
	bool haveMaxs = false;
	std::uint32_t preset = static_cast<std::uint32_t>( azfmt::Preset::SmallRoom );
	float reverbGain = 1.0f;
	float occlusionMultiplier = 1.0f;
	float directLF = 1.0f;
	float directHF = 1.0f;
	float wetLF = 1.0f;
	float wetHF = 1.0f;
	std::uint32_t transitionMs = azfmt::kDefaultTransitionMs;
	std::int32_t priority = 0;
};

enum class TokenKind {
	End,
	Invalid,
	Word,
	String,
	LeftBrace,
	RightBrace
};

struct Token {
	TokenKind kind = TokenKind::End;
	std::string text;
	int line = 1;
	int column = 1;
};

static std::string Lowercase( std::string value ) {
	std::transform( value.begin(), value.end(), value.begin(), []( unsigned char c ) {
		if ( c == '_' ) {
			return '-';
		}
		return static_cast<char>( std::tolower( c ) );
	} );
	return value;
}

static bool ParseFloatToken( const Token &token, float &out, std::string &error ) {
	char *end = nullptr;
	errno = 0;
	const float value = std::strtof( token.text.c_str(), &end );
	if ( token.text.empty() || end == token.text.c_str() || *end != '\0' || errno == ERANGE || !std::isfinite( value ) ) {
		error = "expected floating-point value at line " + std::to_string( token.line );
		return false;
	}
	out = value;
	return true;
}

static bool ParseIntToken( const Token &token, int &out, std::string &error ) {
	char *end = nullptr;
	errno = 0;
	const long value = std::strtol( token.text.c_str(), &end, 10 );
	if ( token.text.empty() || end == token.text.c_str() || *end != '\0' || errno == ERANGE ||
		value < std::numeric_limits<int>::min() || value > std::numeric_limits<int>::max() ) {
		error = "expected integer value at line " + std::to_string( token.line );
		return false;
	}
	out = static_cast<int>( value );
	return true;
}

static bool ParsePresetName( const std::string &text, std::uint32_t &preset ) {
	const std::string normalized = Lowercase( text );
	for ( std::uint32_t i = 0; i < static_cast<std::uint32_t>( azfmt::Preset::Count ); ++i ) {
		if ( normalized == azfmt::kPresetNames[i] ) {
			preset = i;
			return true;
		}
	}
	if ( normalized == "smallroom" ) {
		preset = static_cast<std::uint32_t>( azfmt::Preset::SmallRoom );
		return true;
	}
	if ( normalized == "stoneroom" ) {
		preset = static_cast<std::uint32_t>( azfmt::Preset::StoneRoom );
		return true;
	}
	return false;
}

class Tokenizer {
public:
	explicit Tokenizer( std::string source ) : source_( std::move( source ) ) {}

	Token Next() {
		SkipWhitespaceAndComments();
		Token token;
		token.line = line_;
		token.column = column_;
		if ( !error_.empty() ) {
			token.kind = TokenKind::Invalid;
			token.text = error_;
			token.line = errorLine_;
			token.column = errorColumn_;
			error_.clear();
			return token;
		}

		if ( index_ >= source_.size() ) {
			token.kind = TokenKind::End;
			return token;
		}

		const char c = source_[index_];
		if ( c == '{' ) {
			Advance();
			token.kind = TokenKind::LeftBrace;
			token.text = "{";
			return token;
		}
		if ( c == '}' ) {
			Advance();
			token.kind = TokenKind::RightBrace;
			token.text = "}";
			return token;
		}
		if ( c == '"' ) {
			return ReadString();
		}
		return ReadWord();
	}

private:
	void Advance() {
		if ( index_ >= source_.size() ) {
			return;
		}
		if ( source_[index_] == '\n' ) {
			++line_;
			column_ = 1;
		} else {
			++column_;
		}
		++index_;
	}

	void SkipWhitespaceAndComments() {
		for (;;) {
			while ( index_ < source_.size() && std::isspace( static_cast<unsigned char>( source_[index_] ) ) ) {
				Advance();
			}
			if ( index_ >= source_.size() ) {
				return;
			}
			if ( source_[index_] == '#' ) {
				while ( index_ < source_.size() && source_[index_] != '\n' ) {
					Advance();
				}
				continue;
			}
			if ( source_[index_] == '/' && index_ + 1 < source_.size() && source_[index_ + 1] == '/' ) {
				while ( index_ < source_.size() && source_[index_] != '\n' ) {
					Advance();
				}
				continue;
			}
			if ( source_[index_] == '/' && index_ + 1 < source_.size() && source_[index_ + 1] == '*' ) {
				const int commentLine = line_;
				const int commentColumn = column_;
				Advance();
				Advance();
				while ( index_ + 1 < source_.size() && !( source_[index_] == '*' && source_[index_ + 1] == '/' ) ) {
					Advance();
				}
				if ( index_ + 1 < source_.size() ) {
					Advance();
					Advance();
				} else {
					error_ = "unterminated block comment";
					errorLine_ = commentLine;
					errorColumn_ = commentColumn;
				}
				continue;
			}
			return;
		}
	}

	Token ReadString() {
		Token token;
		token.kind = TokenKind::String;
		token.line = line_;
		token.column = column_;
		Advance();
		while ( index_ < source_.size() ) {
			const char c = source_[index_];
			if ( c == '"' ) {
				Advance();
				return token;
			}
			if ( c == '\\' && index_ + 1 < source_.size() ) {
				Advance();
				const char escaped = source_[index_];
				switch ( escaped ) {
				case 'n':
					token.text.push_back( '\n' );
					break;
				case 't':
					token.text.push_back( '\t' );
					break;
				default:
					token.text.push_back( escaped );
					break;
				}
				Advance();
				continue;
			}
			token.text.push_back( c );
			Advance();
		}
		token.kind = TokenKind::Invalid;
		token.text = "unterminated string";
		return token;
	}

	Token ReadWord() {
		Token token;
		token.kind = TokenKind::Word;
		token.line = line_;
		token.column = column_;
		while ( index_ < source_.size() ) {
			const char c = source_[index_];
			if ( std::isspace( static_cast<unsigned char>( c ) ) || c == '{' || c == '}' || c == '"' ) {
				break;
			}
			if ( c == '#' ) {
				break;
			}
			if ( c == '/' && index_ + 1 < source_.size() && ( source_[index_ + 1] == '/' || source_[index_ + 1] == '*' ) ) {
				break;
			}
			token.text.push_back( c );
			Advance();
		}
		return token;
	}

	std::string source_;
	std::string error_;
	std::size_t index_ = 0;
	int line_ = 1;
	int column_ = 1;
	int errorLine_ = 1;
	int errorColumn_ = 1;
};

class Parser {
public:
	explicit Parser( std::string source ) : tokenizer_( std::move( source ) ) {
		current_ = tokenizer_.Next();
	}

	bool Parse( std::vector<Zone> &zones, std::string &error ) {
		if ( current_.kind == TokenKind::Word && Lowercase( current_.text ) == "audiozones" ) {
			Advance();
			if ( current_.kind == TokenKind::Invalid ) {
				error = current_.text + " at line " + std::to_string( current_.line );
				return false;
			}
			if ( current_.kind != TokenKind::Word || current_.text != "1" ) {
				error = "unsupported or missing audiozones text version at line " + std::to_string( current_.line );
				return false;
			}
			Advance();
		}

		while ( current_.kind != TokenKind::End ) {
			if ( current_.kind == TokenKind::Invalid ) {
				error = current_.text + " at line " + std::to_string( current_.line );
				return false;
			}
			if ( current_.kind != TokenKind::Word || Lowercase( current_.text ) != "zone" ) {
				error = "expected 'zone' at line " + std::to_string( current_.line );
				return false;
			}
			if ( zones.size() >= azfmt::kMaxZones ) {
				error = "too many zones; maximum is " + std::to_string( azfmt::kMaxZones );
				return false;
			}
			Zone zone;
			if ( !ParseZone( zone, error ) ) {
				return false;
			}
			zones.push_back( zone );
		}

		if ( zones.empty() ) {
			error = "no zones were defined";
			return false;
		}
		return true;
	}

private:
	void Advance() {
		current_ = tokenizer_.Next();
	}

	bool ExpectWordLike( Token &token, const char *what, std::string &error ) {
		if ( current_.kind == TokenKind::Invalid ) {
			error = current_.text + " at line " + std::to_string( current_.line );
			return false;
		}
		if ( current_.kind != TokenKind::Word && current_.kind != TokenKind::String ) {
			error = std::string( "expected " ) + what + " at line " + std::to_string( current_.line );
			return false;
		}
		token = current_;
		Advance();
		return true;
	}

	bool ExpectLeftBrace( std::string &error ) {
		if ( current_.kind == TokenKind::Invalid ) {
			error = current_.text + " at line " + std::to_string( current_.line );
			return false;
		}
		if ( current_.kind != TokenKind::LeftBrace ) {
			error = "expected '{' at line " + std::to_string( current_.line );
			return false;
		}
		Advance();
		return true;
	}

	bool ParseVec3( Vec3 &value, std::string &error ) {
		Token token;
		if ( !ExpectWordLike( token, "x value", error ) || !ParseFloatToken( token, value.x, error ) ) {
			return false;
		}
		if ( !ExpectWordLike( token, "y value", error ) || !ParseFloatToken( token, value.y, error ) ) {
			return false;
		}
		if ( !ExpectWordLike( token, "z value", error ) || !ParseFloatToken( token, value.z, error ) ) {
			return false;
		}
		return true;
	}

	bool ParseFloatProperty( float &value, float minimum, float maximum, std::string &error ) {
		Token token;
		if ( !ExpectWordLike( token, "floating-point value", error ) || !ParseFloatToken( token, value, error ) ) {
			return false;
		}
		if ( value < minimum || value > maximum ) {
			std::ostringstream message;
			message << "value at line " << token.line << " is outside allowed range " << minimum << ".." << maximum;
			error = message.str();
			return false;
		}
		return true;
	}

	bool ParseZone( Zone &zone, std::string &error ) {
		Advance();
		Token nameToken;
		if ( !ExpectWordLike( nameToken, "zone name", error ) ) {
			return false;
		}
		zone.name = nameToken.text;
		if ( zone.name.empty() || zone.name.size() > azfmt::kMaxNameBytes ) {
			error = "zone name at line " + std::to_string( nameToken.line ) + " must be 1.." + std::to_string( azfmt::kMaxNameBytes ) + " bytes";
			return false;
		}
		if ( !ExpectLeftBrace( error ) ) {
			return false;
		}

		while ( current_.kind != TokenKind::End && current_.kind != TokenKind::RightBrace ) {
			if ( current_.kind == TokenKind::Invalid ) {
				error = current_.text + " at line " + std::to_string( current_.line );
				return false;
			}
			if ( current_.kind != TokenKind::Word ) {
				error = "expected zone property at line " + std::to_string( current_.line );
				return false;
			}

			const Token propertyToken = current_;
			const std::string property = Lowercase( current_.text );
			Advance();

			if ( property == "bounds" ) {
				if ( !ParseVec3( zone.mins, error ) || !ParseVec3( zone.maxs, error ) ) {
					return false;
				}
				zone.haveMins = true;
				zone.haveMaxs = true;
			} else if ( property == "mins" || property == "min" ) {
				if ( !ParseVec3( zone.mins, error ) ) {
					return false;
				}
				zone.haveMins = true;
			} else if ( property == "maxs" || property == "max" ) {
				if ( !ParseVec3( zone.maxs, error ) ) {
					return false;
				}
				zone.haveMaxs = true;
			} else if ( property == "environment" || property == "preset" ) {
				Token token;
				if ( !ExpectWordLike( token, "environment preset", error ) || !ParsePresetName( token.text, zone.preset ) ) {
					error = "unknown environment preset at line " + std::to_string( token.line );
					return false;
				}
			} else if ( property == "reverbgain" || property == "wetgain" ) {
				if ( !ParseFloatProperty( zone.reverbGain, 0.0f, 4.0f, error ) ) {
					return false;
				}
			} else if ( property == "occlusion" || property == "occlusionmultiplier" ) {
				if ( !ParseFloatProperty( zone.occlusionMultiplier, 0.0f, 4.0f, error ) ) {
					return false;
				}
			} else if ( property == "directlf" ) {
				if ( !ParseFloatProperty( zone.directLF, 0.0f, 1.0f, error ) ) {
					return false;
				}
			} else if ( property == "directhf" ) {
				if ( !ParseFloatProperty( zone.directHF, 0.0f, 1.0f, error ) ) {
					return false;
				}
			} else if ( property == "wetlf" ) {
				if ( !ParseFloatProperty( zone.wetLF, 0.0f, 1.0f, error ) ) {
					return false;
				}
			} else if ( property == "wethf" ) {
				if ( !ParseFloatProperty( zone.wetHF, 0.0f, 1.0f, error ) ) {
					return false;
				}
			} else if ( property == "lpfbias" ) {
				float value = 1.0f;
				if ( !ParseFloatProperty( value, 0.0f, 1.0f, error ) ) {
					return false;
				}
				zone.directHF = value;
				zone.wetHF = value;
			} else if ( property == "hpfbias" ) {
				float value = 1.0f;
				if ( !ParseFloatProperty( value, 0.0f, 1.0f, error ) ) {
					return false;
				}
				zone.directLF = value;
				zone.wetLF = value;
			} else if ( property == "transition" || property == "transitionms" ) {
				int value = 0;
				Token token;
				if ( !ExpectWordLike( token, "transition milliseconds", error ) || !ParseIntToken( token, value, error ) ) {
					return false;
				}
				if ( value < 0 || value > 10000 ) {
					error = "transition at line " + std::to_string( token.line ) + " is outside allowed range 0..10000";
					return false;
				}
				zone.transitionMs = static_cast<std::uint32_t>( value );
			} else if ( property == "priority" ) {
				int value = 0;
				Token token;
				if ( !ExpectWordLike( token, "priority", error ) || !ParseIntToken( token, value, error ) ) {
					return false;
				}
				zone.priority = static_cast<std::int32_t>( value );
			} else {
				error = "unknown zone property '" + propertyToken.text + "' at line " + std::to_string( propertyToken.line );
				return false;
			}
		}

		if ( current_.kind != TokenKind::RightBrace ) {
			error = "unterminated zone '" + zone.name + "'";
			return false;
		}
		Advance();

		if ( !zone.haveMins || !zone.haveMaxs ) {
			error = "zone '" + zone.name + "' is missing bounds";
			return false;
		}
		NormalizeBounds( zone );
		if ( zone.mins.x == zone.maxs.x || zone.mins.y == zone.maxs.y || zone.mins.z == zone.maxs.z ) {
			error = "zone '" + zone.name + "' has zero-volume bounds";
			return false;
		}
		return true;
	}

	static void NormalizeBounds( Zone &zone ) {
		if ( zone.mins.x > zone.maxs.x ) {
			std::swap( zone.mins.x, zone.maxs.x );
		}
		if ( zone.mins.y > zone.maxs.y ) {
			std::swap( zone.mins.y, zone.maxs.y );
		}
		if ( zone.mins.z > zone.maxs.z ) {
			std::swap( zone.mins.z, zone.maxs.z );
		}
	}

	Tokenizer tokenizer_;
	Token current_;
};

static void WriteU8( std::vector<std::uint8_t> &out, std::uint8_t value ) {
	out.push_back( value );
}

static void WriteU32( std::vector<std::uint8_t> &out, std::uint32_t value ) {
	out.push_back( static_cast<std::uint8_t>( value & 0xffu ) );
	out.push_back( static_cast<std::uint8_t>( ( value >> 8u ) & 0xffu ) );
	out.push_back( static_cast<std::uint8_t>( ( value >> 16u ) & 0xffu ) );
	out.push_back( static_cast<std::uint8_t>( ( value >> 24u ) & 0xffu ) );
}

static void WriteI32( std::vector<std::uint8_t> &out, std::int32_t value ) {
	WriteU32( out, static_cast<std::uint32_t>( value ) );
}

static void WriteF32( std::vector<std::uint8_t> &out, float value ) {
	static_assert( sizeof( float ) == sizeof( std::uint32_t ), "FnQuake3 audio zone files require 32-bit floats" );
	std::uint32_t bits = 0;
	std::memcpy( &bits, &value, sizeof( bits ) );
	WriteU32( out, bits );
}

static void WriteVec3( std::vector<std::uint8_t> &out, const Vec3 &value ) {
	WriteF32( out, value.x );
	WriteF32( out, value.y );
	WriteF32( out, value.z );
}

static std::vector<std::uint8_t> BuildBinary( const std::vector<Zone> &zones ) {
	std::vector<std::uint8_t> binary;
	binary.reserve( 12u + zones.size() * 80u );
	binary.insert( binary.end(), std::begin( azfmt::kMagic ), std::end( azfmt::kMagic ) );
	WriteU32( binary, azfmt::kVersion );
	WriteU32( binary, static_cast<std::uint32_t>( zones.size() ) );

	for ( const Zone &zone : zones ) {
		WriteVec3( binary, zone.mins );
		WriteVec3( binary, zone.maxs );
		WriteU32( binary, zone.preset );
		WriteF32( binary, zone.reverbGain );
		WriteF32( binary, zone.occlusionMultiplier );
		WriteF32( binary, zone.directLF );
		WriteF32( binary, zone.directHF );
		WriteF32( binary, zone.wetLF );
		WriteF32( binary, zone.wetHF );
		WriteU32( binary, zone.transitionMs );
		WriteI32( binary, zone.priority );
		WriteU8( binary, static_cast<std::uint8_t>( zone.name.size() ) );
		binary.insert( binary.end(), zone.name.begin(), zone.name.end() );
	}

	return binary;
}

static bool ReadWholeFile( const std::filesystem::path &path, std::string &contents, std::string &error ) {
	std::error_code ec;
	const std::uintmax_t size = std::filesystem::file_size( path, ec );
	if ( !ec && size > azfmt::kMaxFileBytes ) {
		error = "source file is too large";
		return false;
	}

	std::ifstream file( path, std::ios::binary );
	if ( !file ) {
		error = "could not open " + path.string();
		return false;
	}
	std::ostringstream stream;
	stream << file.rdbuf();
	contents = stream.str();
	if ( contents.size() > azfmt::kMaxFileBytes ) {
		error = "source file is too large";
		return false;
	}
	return true;
}

static bool WriteWholeFile( const std::filesystem::path &path, const std::vector<std::uint8_t> &contents, std::string &error ) {
	if ( path.has_parent_path() ) {
		std::error_code ec;
		std::filesystem::create_directories( path.parent_path(), ec );
		if ( ec ) {
			error = "could not create directory " + path.parent_path().string() + ": " + ec.message();
			return false;
		}
	}

	std::ofstream file( path, std::ios::binary );
	if ( !file ) {
		error = "could not write " + path.string();
		return false;
	}
	file.write( reinterpret_cast<const char *>( contents.data() ), static_cast<std::streamsize>( contents.size() ) );
	if ( !file ) {
		error = "failed while writing " + path.string();
		return false;
	}
	return true;
}

static std::filesystem::path DefaultOutputPath( std::filesystem::path input ) {
	input.replace_extension( ".azb" );
	return input;
}

static bool ReadU8( const std::vector<std::uint8_t> &data, std::size_t &offset, std::uint8_t &out ) {
	if ( offset >= data.size() ) {
		return false;
	}
	out = data[offset++];
	return true;
}

static bool ReadU32( const std::vector<std::uint8_t> &data, std::size_t &offset, std::uint32_t &out ) {
	if ( offset > data.size() || data.size() - offset < 4u ) {
		return false;
	}
	out = static_cast<std::uint32_t>( data[offset] ) |
		( static_cast<std::uint32_t>( data[offset + 1u] ) << 8u ) |
		( static_cast<std::uint32_t>( data[offset + 2u] ) << 16u ) |
		( static_cast<std::uint32_t>( data[offset + 3u] ) << 24u );
	offset += 4u;
	return true;
}

static bool ReadI32( const std::vector<std::uint8_t> &data, std::size_t &offset, std::int32_t &out ) {
	std::uint32_t value = 0;
	if ( !ReadU32( data, offset, value ) ) {
		return false;
	}
	out = static_cast<std::int32_t>( value );
	return true;
}

static bool ReadF32( const std::vector<std::uint8_t> &data, std::size_t &offset, float &out ) {
	std::uint32_t bits = 0;
	if ( !ReadU32( data, offset, bits ) ) {
		return false;
	}
	std::memcpy( &out, &bits, sizeof( out ) );
	return std::isfinite( out );
}

static bool ReadVec3( const std::vector<std::uint8_t> &data, std::size_t &offset, Vec3 &out ) {
	return ReadF32( data, offset, out.x ) &&
		ReadF32( data, offset, out.y ) &&
		ReadF32( data, offset, out.z );
}

static bool LoadBinary( const std::filesystem::path &path, std::vector<Zone> &zones, std::string &error ) {
	std::error_code ec;
	const std::uintmax_t size = std::filesystem::file_size( path, ec );
	if ( !ec && size > azfmt::kMaxFileBytes ) {
		error = "file is too large";
		return false;
	}

	std::ifstream file( path, std::ios::binary );
	if ( !file ) {
		error = "could not open " + path.string();
		return false;
	}
	const std::vector<std::uint8_t> data( ( std::istreambuf_iterator<char>( file ) ), std::istreambuf_iterator<char>() );
	if ( data.size() > azfmt::kMaxFileBytes ) {
		error = "file is too large";
		return false;
	}
	if ( data.size() < 12u || !std::equal( std::begin( azfmt::kMagic ), std::end( azfmt::kMagic ), data.begin() ) ) {
		error = "bad audio-zone magic";
		return false;
	}

	std::size_t offset = 4u;
	std::uint32_t version = 0;
	std::uint32_t zoneCount = 0;
	if ( !ReadU32( data, offset, version ) || !ReadU32( data, offset, zoneCount ) ) {
		error = "truncated audio-zone header";
		return false;
	}
	if ( version != azfmt::kVersion ) {
		error = "unsupported audio-zone version " + std::to_string( version );
		return false;
	}
	if ( zoneCount > azfmt::kMaxZones ) {
		error = "too many zones in file";
		return false;
	}
	if ( zoneCount == 0 ) {
		error = "no zones in file";
		return false;
	}

	zones.clear();
	zones.reserve( zoneCount );
	for ( std::uint32_t i = 0; i < zoneCount; ++i ) {
		Zone zone;
		std::uint8_t nameLength = 0;
		if ( !ReadVec3( data, offset, zone.mins ) ||
			!ReadVec3( data, offset, zone.maxs ) ||
			!ReadU32( data, offset, zone.preset ) ||
			!ReadF32( data, offset, zone.reverbGain ) ||
			!ReadF32( data, offset, zone.occlusionMultiplier ) ||
			!ReadF32( data, offset, zone.directLF ) ||
			!ReadF32( data, offset, zone.directHF ) ||
			!ReadF32( data, offset, zone.wetLF ) ||
			!ReadF32( data, offset, zone.wetHF ) ||
			!ReadU32( data, offset, zone.transitionMs ) ||
			!ReadI32( data, offset, zone.priority ) ||
			!ReadU8( data, offset, nameLength ) ) {
			error = "truncated zone record";
			return false;
		}
		if ( zone.preset >= static_cast<std::uint32_t>( azfmt::Preset::Count ) ) {
			error = "zone record has unknown preset index";
			return false;
		}
		if ( nameLength == 0 || nameLength > azfmt::kMaxNameBytes ||
			offset > data.size() || data.size() - offset < nameLength ) {
			error = "zone record has invalid name length";
			return false;
		}
		zone.name.assign( reinterpret_cast<const char *>( data.data() + offset ), nameLength );
		offset += nameLength;
		zones.push_back( zone );
	}
	if ( offset != data.size() ) {
		error = "audio-zone file has trailing bytes";
		return false;
	}
	return true;
}

static int CompileCommand( int argc, char **argv ) {
	std::filesystem::path input;
	std::filesystem::path output;

	for ( int i = 1; i < argc; ++i ) {
		const std::string arg = argv[i];
		if ( arg == "-o" || arg == "--output" ) {
			if ( i + 1 >= argc ) {
				std::cerr << "missing output path after " << arg << "\n";
				return 2;
			}
			output = argv[++i];
		} else if ( arg == "-h" || arg == "--help" ) {
			return 2;
		} else if ( input.empty() ) {
			input = arg;
		} else {
			std::cerr << "unexpected argument: " << arg << "\n";
			return 2;
		}
	}

	if ( input.empty() ) {
		return 2;
	}
	if ( output.empty() ) {
		output = DefaultOutputPath( input );
	}

	std::string source;
	std::string error;
	if ( !ReadWholeFile( input, source, error ) ) {
		std::cerr << error << "\n";
		return 1;
	}

	std::vector<Zone> zones;
	Parser parser( source );
	if ( !parser.Parse( zones, error ) ) {
		std::cerr << input.string() << ": " << error << "\n";
		return 1;
	}

	const std::vector<std::uint8_t> binary = BuildBinary( zones );
	if ( !WriteWholeFile( output, binary, error ) ) {
		std::cerr << error << "\n";
		return 1;
	}

	std::cout << "wrote " << zones.size() << " audio zone" << ( zones.size() == 1u ? "" : "s" )
		<< " to " << output.string() << "\n";
	return 0;
}

static int DumpCommand( int argc, char **argv ) {
	if ( argc != 3 ) {
		return 2;
	}
	std::vector<Zone> zones;
	std::string error;
	if ( !LoadBinary( argv[2], zones, error ) ) {
		std::cerr << argv[2] << ": " << error << "\n";
		return 1;
	}
	std::cout << "audiozones version " << azfmt::kVersion << ", zones " << zones.size() << "\n";
	for ( const Zone &zone : zones ) {
		const char *presetName = zone.preset < static_cast<std::uint32_t>( azfmt::Preset::Count )
			? azfmt::kPresetNames[zone.preset]
			: "unknown";
		std::cout << "zone \"" << zone.name << "\""
			<< " preset " << presetName
			<< " bounds " << zone.mins.x << ' ' << zone.mins.y << ' ' << zone.mins.z
			<< " -> " << zone.maxs.x << ' ' << zone.maxs.y << ' ' << zone.maxs.z
			<< " priority " << zone.priority
			<< " transition " << zone.transitionMs
			<< " reverbGain " << zone.reverbGain
			<< " occlusion " << zone.occlusionMultiplier
			<< " directLF/HF " << zone.directLF << '/' << zone.directHF
			<< " wetLF/HF " << zone.wetLF << '/' << zone.wetHF
			<< "\n";
	}
	return 0;
}

static void PrintUsage( const char *argv0 ) {
	std::cerr
		<< "Usage:\n"
		<< "  " << argv0 << " [-o output.azb] input.audiozones\n"
		<< "  " << argv0 << " --dump input.azb\n\n"
		<< "Text format:\n"
		<< "  audiozones 1\n"
		<< "  zone \"atrium\" {\n"
		<< "    bounds -512 -512 -64 512 512 384\n"
		<< "    environment hall\n"
		<< "    reverbGain 1.1\n"
		<< "    occlusionMultiplier 0.85\n"
		<< "    lpfBias 0.95\n"
		<< "    hpfBias 1.0\n"
		<< "    transitionMs 900\n"
		<< "    priority 10\n"
		<< "  }\n";
}

} // namespace

int main( int argc, char **argv ) {
	if ( argc >= 2 && std::string( argv[1] ) == "--dump" ) {
		const int result = DumpCommand( argc, argv );
		if ( result == 2 ) {
			PrintUsage( argv[0] );
		}
		return result;
	}

	const int result = CompileCommand( argc, argv );
	if ( result == 2 ) {
		PrintUsage( argv[0] );
	}
	return result;
}
