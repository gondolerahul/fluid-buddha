<?php
/**
 * Pure helpers (no WordPress calls), so they can be unit-tested with plain PHP.
 *
 * @package FluidBuddha
 */

if ( ! defined( 'ABSPATH' ) && ! defined( 'FLUIDBUDDHA_TESTING' ) ) {
	exit;
}

/**
 * Read an install code from the FluidBuddha console:
 * "https://fbk_abc123@agent.example.com" — the widget key and the server in one string.
 *
 * @param string $code The install code as pasted.
 * @return array{server:string,key:string}|null Null when it isn't usable.
 */
function fluidbuddha_parse_install_code( $code ) {
	$code = trim( (string) $code );
	if ( ! preg_match( '#^(https?)://([^@/\s?\#]+)@([^\s?\#]+)$#', $code, $m ) ) {
		return null;
	}
	$key = rawurldecode( $m[2] );
	if ( ! preg_match( '/^fbk_[A-Za-z0-9_-]{8,200}$/', $key ) ) {
		return null;
	}
	$rest = rtrim( $m[3], '/' );
	// Host (optionally :port) and an optional path, nothing else.
	if ( ! preg_match( '#^[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?$#', $rest ) ) {
		return null;
	}
	return array(
		'server' => $m[1] . '://' . $rest,
		'key'    => $key,
	);
}

/**
 * Whether a request path matches one of the exclusion patterns
 * (one per line, "*" matches anything, e.g. "/checkout*" or "/account/*").
 *
 * @param string $path     Request path, e.g. "/checkout/step-2".
 * @param string $patterns Newline-separated patterns.
 * @return bool
 */
function fluidbuddha_path_excluded( $path, $patterns ) {
	$path = '/' . ltrim( (string) $path, '/' );
	foreach ( preg_split( '/\r\n|\r|\n/', (string) $patterns ) as $pattern ) {
		$pattern = trim( $pattern );
		if ( '' === $pattern ) {
			continue;
		}
		$pattern = '/' . ltrim( $pattern, '/' );
		$regex   = '#^' . str_replace( '\*', '.*', preg_quote( $pattern, '#' ) ) . '$#i';
		if ( preg_match( $regex, $path ) ) {
			return true;
		}
	}
	return false;
}

/**
 * The data-* attributes for the loader script tag.
 *
 * @param array $target   From fluidbuddha_parse_install_code().
 * @param array $settings Plugin settings (position, lang).
 * @return array<string,string>
 */
function fluidbuddha_loader_attributes( $target, $settings ) {
	$attrs = array( 'data-key' => $target['key'] );
	if ( isset( $settings['position'] ) && in_array( $settings['position'], array( 'bottom-right', 'bottom-left' ), true ) ) {
		$attrs['data-position'] = $settings['position'];
	}
	if ( isset( $settings['lang'] ) && in_array( $settings['lang'], array( 'en', 'hi' ), true ) ) {
		$attrs['data-lang'] = $settings['lang'];
	}
	return $attrs;
}
