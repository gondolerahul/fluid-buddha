<?php
/**
 * Plugin Name:       FluidBuddha AI Agent
 * Plugin URI:        https://github.com/gondolerahul/fluid-buddha
 * Description:       Adds the FluidBuddha voice and chat sales agent to your site. Paste your install code from the FluidBuddha console and you're done.
 * Version:           2.0.0
 * Requires at least: 5.8
 * Requires PHP:      7.4
 * Author:            FluidBuddha
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       fluidbuddha
 *
 * @package FluidBuddha
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'FLUIDBUDDHA_VERSION', '2.0.0' );
define( 'FLUIDBUDDHA_OPTION', 'fluidbuddha_settings' );

require_once __DIR__ . '/includes/functions.php';

/**
 * Saved settings with defaults.
 *
 * @return array
 */
function fluidbuddha_settings() {
	$saved = get_option( FLUIDBUDDHA_OPTION, array() );
	return wp_parse_args(
		is_array( $saved ) ? $saved : array(),
		array(
			'install_code'   => '',
			'position'       => '',
			'lang'           => 'auto',
			'exclude'        => '',
			'hide_for_staff' => 0,
		)
	);
}

/* ---------------------------------------------------------------------------
 * Front end: the loader script, on public pages only.
 * ------------------------------------------------------------------------- */

/**
 * Whether the agent should appear on this request.
 *
 * @param array $settings Plugin settings.
 * @return bool
 */
function fluidbuddha_should_show( $settings ) {
	if ( is_admin() || is_feed() || is_robots() || is_trackback() || wp_doing_ajax() || is_customize_preview() ) {
		return false;
	}
	if ( ! empty( $settings['hide_for_staff'] ) && current_user_can( 'edit_posts' ) ) {
		return false;
	}
	$uri  = isset( $_SERVER['REQUEST_URI'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '/';
	$path = (string) wp_parse_url( $uri, PHP_URL_PATH );
	return ! fluidbuddha_path_excluded( $path, $settings['exclude'] );
}

/**
 * Enqueue the loader script.
 */
function fluidbuddha_enqueue() {
	$settings = fluidbuddha_settings();
	$target   = fluidbuddha_parse_install_code( $settings['install_code'] );
	if ( ! $target || ! fluidbuddha_should_show( $settings ) ) {
		return;
	}
	wp_enqueue_script(
		'fluidbuddha-loader',
		$target['server'] . '/widget/loader.js',
		array(),
		null, // The server versions the widget itself; no ?ver= on the loader.
		array(
			'in_footer' => true,
			'strategy'  => 'async',
		)
	);
}
add_action( 'wp_enqueue_scripts', 'fluidbuddha_enqueue' );

/**
 * Add the widget key and options to the loader's tag.
 *
 * @param string $tag    The script tag.
 * @param string $handle Script handle.
 * @return string
 */
function fluidbuddha_script_tag( $tag, $handle ) {
	if ( 'fluidbuddha-loader' !== $handle ) {
		return $tag;
	}
	$settings = fluidbuddha_settings();
	$target   = fluidbuddha_parse_install_code( $settings['install_code'] );
	if ( ! $target ) {
		return $tag;
	}
	$extra = '';
	foreach ( fluidbuddha_loader_attributes( $target, $settings ) as $name => $value ) {
		$extra .= ' ' . $name . '="' . esc_attr( $value ) . '"';
	}
	// Before WordPress 6.3 there's no loading strategy; make it async anyway.
	if ( false === strpos( $tag, ' async' ) ) {
		$extra .= ' async';
	}
	return preg_replace( '/<script /', '<script' . $extra . ' ', $tag, 1 );
}
add_filter( 'script_loader_tag', 'fluidbuddha_script_tag', 10, 2 );

/**
 * Connect to the server early.
 *
 * @param array  $urls          URLs to print for resource hints.
 * @param string $relation_type The relation type.
 * @return array
 */
function fluidbuddha_resource_hints( $urls, $relation_type ) {
	if ( 'preconnect' === $relation_type && ! is_admin() ) {
		$target = fluidbuddha_parse_install_code( fluidbuddha_settings()['install_code'] );
		// WordPress prints only scheme://host for a preconnect, so skip servers
		// on another port, where the hint would point somewhere else.
		if ( $target && null === wp_parse_url( $target['server'], PHP_URL_PORT ) ) {
			$urls[] = array(
				'href'        => $target['server'],
				'crossorigin' => 'anonymous',
			);
		}
	}
	return $urls;
}
add_filter( 'wp_resource_hints', 'fluidbuddha_resource_hints', 10, 2 );

/* ---------------------------------------------------------------------------
 * Admin: Settings → FluidBuddha.
 * ------------------------------------------------------------------------- */

/**
 * Register the setting.
 */
function fluidbuddha_register_settings() {
	register_setting(
		'fluidbuddha',
		FLUIDBUDDHA_OPTION,
		array(
			'type'              => 'array',
			'sanitize_callback' => 'fluidbuddha_sanitize',
			'default'           => array(),
		)
	);
}
add_action( 'admin_init', 'fluidbuddha_register_settings' );

/**
 * Sanitize the settings form.
 *
 * @param mixed $input Submitted values.
 * @return array
 */
function fluidbuddha_sanitize( $input ) {
	$input = is_array( $input ) ? $input : array();
	$out   = array(
		'install_code'   => '',
		'position'       => '',
		'lang'           => 'auto',
		'exclude'        => '',
		'hide_for_staff' => empty( $input['hide_for_staff'] ) ? 0 : 1,
	);
	$code = isset( $input['install_code'] ) ? trim( sanitize_text_field( $input['install_code'] ) ) : '';
	if ( '' !== $code ) {
		if ( fluidbuddha_parse_install_code( $code ) ) {
			$out['install_code'] = $code;
		} else {
			add_settings_error(
				FLUIDBUDDHA_OPTION,
				'fluidbuddha_code',
				__( 'That install code isn’t valid. Copy it from the FluidBuddha console: your website → Install → WordPress. It looks like https://fbk_…@your-server.', 'fluidbuddha' )
			);
			$out['install_code'] = fluidbuddha_settings()['install_code']; // keep the working one
		}
	}
	if ( isset( $input['position'] ) && in_array( $input['position'], array( 'bottom-right', 'bottom-left' ), true ) ) {
		$out['position'] = $input['position'];
	}
	if ( isset( $input['lang'] ) && in_array( $input['lang'], array( 'auto', 'en', 'hi' ), true ) ) {
		$out['lang'] = $input['lang'];
	}
	if ( isset( $input['exclude'] ) ) {
		$lines          = array_filter( array_map( 'trim', preg_split( '/\r\n|\r|\n/', sanitize_textarea_field( $input['exclude'] ) ) ) );
		$out['exclude'] = implode( "\n", array_slice( $lines, 0, 100 ) );
	}
	return $out;
}

/**
 * Add the settings page.
 */
function fluidbuddha_admin_menu() {
	add_options_page(
		__( 'FluidBuddha', 'fluidbuddha' ),
		__( 'FluidBuddha', 'fluidbuddha' ),
		'manage_options',
		'fluidbuddha',
		'fluidbuddha_render_settings'
	);
}
add_action( 'admin_menu', 'fluidbuddha_admin_menu' );

/**
 * Ask the server what the key resolves to (no agent turn, costs nothing).
 *
 * @param array $target Server and key.
 * @return array{ok:bool,message:string}
 */
function fluidbuddha_check_connection( $target ) {
	$response = wp_remote_get(
		add_query_arg( 'key', rawurlencode( $target['key'] ), $target['server'] . '/widget/config' ),
		array( 'timeout' => 5 )
	);
	if ( is_wp_error( $response ) ) {
		return array(
			'ok'      => false,
			/* translators: %s: error message */
			'message' => sprintf( __( 'Can’t reach the FluidBuddha server: %s', 'fluidbuddha' ), $response->get_error_message() ),
		);
	}
	$code = (int) wp_remote_retrieve_response_code( $response );
	$body = json_decode( wp_remote_retrieve_body( $response ), true );
	if ( 200 !== $code || ! is_array( $body ) ) {
		return array(
			'ok'      => false,
			'message' => 403 === $code
				? __( 'The server doesn’t recognise this key. It may have been rotated — copy the install code again.', 'fluidbuddha' )
				/* translators: %d: HTTP status code */
				: sprintf( __( 'Unexpected answer from the server (HTTP %d).', 'fluidbuddha' ), $code ),
		);
	}
	return array(
		'ok'      => true,
		'message' => sprintf(
			/* translators: 1: agent name, 2: company name */
			__( 'Connected: %1$s, the agent for %2$s.', 'fluidbuddha' ),
			isset( $body['agent_name'] ) ? (string) $body['agent_name'] : 'Pragya',
			isset( $body['company_name'] ) ? (string) $body['company_name'] : ''
		),
	);
}

/**
 * Render the settings page.
 */
function fluidbuddha_render_settings() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	$s      = fluidbuddha_settings();
	$target = fluidbuddha_parse_install_code( $s['install_code'] );
	$check  = $target ? fluidbuddha_check_connection( $target ) : null;
	$name   = FLUIDBUDDHA_OPTION;
	?>
	<div class="wrap">
		<h1><?php esc_html_e( 'FluidBuddha AI Agent', 'fluidbuddha' ); ?></h1>
		<?php settings_errors( FLUIDBUDDHA_OPTION ); ?>
		<?php if ( $check ) : ?>
			<div class="notice notice-<?php echo $check['ok'] ? 'success' : 'error'; ?> inline"><p><?php echo esc_html( $check['message'] ); ?></p></div>
		<?php endif; ?>
		<p><?php esc_html_e( 'The agent answers your visitors by voice and chat, from your own content. Settings such as its tier, design, colour, knowledge and greeting live in the FluidBuddha console.', 'fluidbuddha' ); ?></p>
		<form method="post" action="options.php">
			<?php settings_fields( 'fluidbuddha' ); ?>
			<table class="form-table" role="presentation">
				<tr>
					<th scope="row"><label for="fb-code"><?php esc_html_e( 'Install code', 'fluidbuddha' ); ?></label></th>
					<td>
						<input type="text" id="fb-code" class="large-text code" name="<?php echo esc_attr( $name ); ?>[install_code]"
							value="<?php echo esc_attr( $s['install_code'] ); ?>" placeholder="https://fbk_…@your-fluidbuddha-server" autocomplete="off" spellcheck="false" />
						<p class="description"><?php esc_html_e( 'From the FluidBuddha console: your website → Install → WordPress. Leave empty to remove the agent.', 'fluidbuddha' ); ?></p>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="fb-position"><?php esc_html_e( 'Position', 'fluidbuddha' ); ?></label></th>
					<td>
						<select id="fb-position" name="<?php echo esc_attr( $name ); ?>[position]">
							<option value="" <?php selected( $s['position'], '' ); ?>><?php esc_html_e( 'Default (bottom right)', 'fluidbuddha' ); ?></option>
							<option value="bottom-right" <?php selected( $s['position'], 'bottom-right' ); ?>><?php esc_html_e( 'Bottom right', 'fluidbuddha' ); ?></option>
							<option value="bottom-left" <?php selected( $s['position'], 'bottom-left' ); ?>><?php esc_html_e( 'Bottom left', 'fluidbuddha' ); ?></option>
						</select>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="fb-lang"><?php esc_html_e( 'Widget language', 'fluidbuddha' ); ?></label></th>
					<td>
						<select id="fb-lang" name="<?php echo esc_attr( $name ); ?>[lang]">
							<option value="auto" <?php selected( $s['lang'], 'auto' ); ?>><?php esc_html_e( 'Your console setting / the visitor’s browser', 'fluidbuddha' ); ?></option>
							<option value="en" <?php selected( $s['lang'], 'en' ); ?>><?php esc_html_e( 'English', 'fluidbuddha' ); ?></option>
							<option value="hi" <?php selected( $s['lang'], 'hi' ); ?>><?php esc_html_e( 'Hindi', 'fluidbuddha' ); ?></option>
						</select>
						<p class="description"><?php esc_html_e( 'Hindi needs Hindi switched on for the website in the console.', 'fluidbuddha' ); ?></p>
					</td>
				</tr>
				<tr>
					<th scope="row"><label for="fb-exclude"><?php esc_html_e( 'Hide on these pages', 'fluidbuddha' ); ?></label></th>
					<td>
						<textarea id="fb-exclude" class="large-text code" rows="4" name="<?php echo esc_attr( $name ); ?>[exclude]" placeholder="/checkout*&#10;/my-account/*"><?php echo esc_textarea( $s['exclude'] ); ?></textarea>
						<p class="description"><?php esc_html_e( 'One path per line; * matches anything. The agent never appears in wp-admin.', 'fluidbuddha' ); ?></p>
					</td>
				</tr>
				<tr>
					<th scope="row"><?php esc_html_e( 'Your team', 'fluidbuddha' ); ?></th>
					<td>
						<label><input type="checkbox" name="<?php echo esc_attr( $name ); ?>[hide_for_staff]" value="1" <?php checked( ! empty( $s['hide_for_staff'] ) ); ?> />
							<?php esc_html_e( 'Hide the agent from logged-in editors and admins (keeps your own visits out of the numbers)', 'fluidbuddha' ); ?></label>
					</td>
				</tr>
			</table>
			<?php submit_button(); ?>
		</form>
	</div>
	<?php
}

/**
 * "Settings" link on the Plugins screen.
 *
 * @param array $links Action links.
 * @return array
 */
function fluidbuddha_action_links( $links ) {
	array_unshift(
		$links,
		'<a href="' . esc_url( admin_url( 'options-general.php?page=fluidbuddha' ) ) . '">' . esc_html__( 'Settings', 'fluidbuddha' ) . '</a>'
	);
	return $links;
}
add_filter( 'plugin_action_links_' . plugin_basename( __FILE__ ), 'fluidbuddha_action_links' );

/**
 * Remind admins to finish setup, on the Plugins screen only.
 */
function fluidbuddha_setup_notice() {
	$screen = function_exists( 'get_current_screen' ) ? get_current_screen() : null;
	if ( ! $screen || 'plugins' !== $screen->id || ! current_user_can( 'manage_options' ) ) {
		return;
	}
	if ( fluidbuddha_parse_install_code( fluidbuddha_settings()['install_code'] ) ) {
		return;
	}
	printf(
		'<div class="notice notice-info"><p>%s <a href="%s">%s</a></p></div>',
		esc_html__( 'FluidBuddha is almost ready: paste your install code to put the agent on your site.', 'fluidbuddha' ),
		esc_url( admin_url( 'options-general.php?page=fluidbuddha' ) ),
		esc_html__( 'Open settings', 'fluidbuddha' )
	);
}
add_action( 'admin_notices', 'fluidbuddha_setup_notice' );
