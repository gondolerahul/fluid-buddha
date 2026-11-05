<?php
/**
 * Remove the plugin's settings when it is deleted.
 *
 * @package FluidBuddha
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'fluidbuddha_settings' );
