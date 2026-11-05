<?php
/**
 * Unit tests for the plugin's pure helpers. Plain PHP, no WordPress needed:
 *   php integrations/wordpress/tests/test-functions.php
 *
 * @package FluidBuddha
 */

define( 'FLUIDBUDDHA_TESTING', true );
require __DIR__ . '/../fluidbuddha/includes/functions.php';

$failures = 0;
function check( $cond, $msg ) {
	global $failures;
	echo ( $cond ? 'PASS' : 'FAIL' ) . "  $msg\n";
	if ( ! $cond ) {
		$failures++;
	}
}

// Install codes.
$t = fluidbuddha_parse_install_code( '  https://fbk_abcdefgh12345678@agent.example.com/  ' );
check( $t === array( 'server' => 'https://agent.example.com', 'key' => 'fbk_abcdefgh12345678' ), 'install code gives server and key' );
$t = fluidbuddha_parse_install_code( 'http://fbk_abcd-_12345678@localhost:8081/fb' );
check( $t === array( 'server' => 'http://localhost:8081/fb', 'key' => 'fbk_abcd-_12345678' ), 'port and path are kept' );
foreach ( array(
	'',
	'fbk_abcdefgh12345678',
	'https://agent.example.com',
	'https://notakey@agent.example.com',
	'javascript://fbk_abcdefgh12345678@x',
	'https://fbk_abcdefgh12345678@agent.example.com?x=1',
	'https://fbk_abcdefgh12345678@agent.example.com/"><script>',
	'https://fbk_abcdefgh12345678@agent.example.com/ x',
	'https://fbk_abc%22%3E12345678@agent.example.com',
) as $bad ) {
	check( null === fluidbuddha_parse_install_code( $bad ), "refused: $bad" );
}

// Exclusions.
$patterns = "/checkout*\n  /my-account/*  \n\n/exact";
check( fluidbuddha_path_excluded( '/checkout', $patterns ), 'prefix pattern matches' );
check( fluidbuddha_path_excluded( '/checkout/step-2', $patterns ), 'prefix pattern matches deeper paths' );
check( fluidbuddha_path_excluded( '/my-account/orders', $patterns ), 'directory pattern matches' );
check( ! fluidbuddha_path_excluded( '/my-account', $patterns ), 'directory pattern needs the slash' );
check( fluidbuddha_path_excluded( '/EXACT', $patterns ), 'case-insensitive exact match' );
check( ! fluidbuddha_path_excluded( '/exact/more', $patterns ), 'exact pattern is exact' );
check( ! fluidbuddha_path_excluded( '/pricing', $patterns ), 'other pages show the agent' );
check( ! fluidbuddha_path_excluded( '/a.b', '/a?b' ), 'regex characters are literal' );
check( ! fluidbuddha_path_excluded( '/anything', '' ), 'no patterns, nothing excluded' );

// Loader attributes.
$target = array( 'server' => 'https://agent.example.com', 'key' => 'fbk_abcdefgh12345678' );
check( fluidbuddha_loader_attributes( $target, array( 'position' => '', 'lang' => 'auto' ) ) === array( 'data-key' => 'fbk_abcdefgh12345678' ), 'defaults add only the key' );
check(
	fluidbuddha_loader_attributes( $target, array( 'position' => 'bottom-left', 'lang' => 'hi' ) )
		=== array( 'data-key' => 'fbk_abcdefgh12345678', 'data-position' => 'bottom-left', 'data-lang' => 'hi' ),
	'position and language are passed'
);
check( fluidbuddha_loader_attributes( $target, array( 'position' => 'top"', 'lang' => 'xx' ) ) === array( 'data-key' => 'fbk_abcdefgh12345678' ), 'unknown values are dropped' );

echo $failures ? "\n$failures FAILED\n" : "\nALL PASS\n";
exit( $failures ? 1 : 0 );
