"""
Google Tag Manager custom template for this server (M2-10).

GTM runs templates in a sandbox: a template may only inject scripts from the
addresses its ``inject_script`` permission lists, and it can't set attributes
on the injected tag. So the template is generated per server — the permission
names exactly ``<server>/widget/loader.js`` — and passes the widget key and
options in the loader's query string, which the loader turns into the widget's
``data-*`` settings.

The file follows GTM's export format (the sections Tag Manager writes when you
export a template), including a ``___TESTS___`` section in GTM's own test
format that runs in the template editor.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

KEY_PATTERN = r"^fbk_[A-Za-z0-9_-]+$"

_TERMS = """By creating or modifying this file you agree to Google Tag Manager's Community
Template Gallery Developer Terms of Service available at
https://developers.google.com/tag-manager/gallery-tos (or such other URL as
Google may provide), as modified from time to time."""

_PARAMETERS = [
    {
        "type": "TEXT",
        "name": "widgetKey",
        "displayName": "Widget key",
        "help": "From the FluidBuddha console: your website → Install. Starts with fbk_.",
        "simpleValueType": True,
        "valueValidators": [{"type": "NON_EMPTY"}, {"type": "REGEX", "args": [KEY_PATTERN]}],
    },
    {
        "type": "SELECT",
        "name": "position",
        "displayName": "Position",
        "selectItems": [
            {"value": "bottom-right", "displayValue": "Bottom right"},
            {"value": "bottom-left", "displayValue": "Bottom left"},
        ],
        "simpleValueType": True,
        "defaultValue": "bottom-right",
    },
    {
        "type": "SELECT",
        "name": "lang",
        "displayName": "Widget language",
        "help": "Hindi needs Hindi switched on for the website in the console.",
        "selectItems": [
            {"value": "auto", "displayValue": "The website's setting / the visitor's browser"},
            {"value": "en", "displayValue": "English"},
            {"value": "hi", "displayValue": "Hindi"},
        ],
        "simpleValueType": True,
        "defaultValue": "auto",
    },
]

_CODE = """const injectScript = require('injectScript');
const encodeUriComponent = require('encodeUriComponent');

const LOADER = '__LOADER__';

let url = LOADER + '?key=' + encodeUriComponent(data.widgetKey);
if (data.position === 'bottom-left') {
  url = url + '&position=bottom-left';
}
if (data.lang === 'en' || data.lang === 'hi') {
  url = url + '&lang=' + data.lang;
}

// The cache token makes GTM inject it once per page, however many triggers fire.
injectScript(url, data.gtmOnSuccess, data.gtmOnFailure, 'fluidbuddha');
"""

_TESTS = """scenarios:
- name: Injects the loader with the widget key
  code: |-
    const mockData = {widgetKey: 'fbk_test_123', position: 'bottom-right', lang: 'auto'};
    let injected;
    mock('injectScript', function(url, onSuccess, onFailure, token) {
      injected = url;
      onSuccess();
    });
    runCode(mockData);
    assertThat(injected).isEqualTo('__LOADER__?key=fbk_test_123');
    assertApi('gtmOnSuccess').wasCalled();
- name: Passes position and language
  code: |-
    const mockData = {widgetKey: 'fbk_test_123', position: 'bottom-left', lang: 'hi'};
    let injected;
    mock('injectScript', function(url, onSuccess) {
      injected = url;
      onSuccess();
    });
    runCode(mockData);
    assertThat(injected).isEqualTo('__LOADER__?key=fbk_test_123&position=bottom-left&lang=hi');
- name: Reports a failure when the script can't load
  code: |-
    mock('injectScript', function(url, onSuccess, onFailure) {
      onFailure();
    });
    runCode({widgetKey: 'fbk_test_123', position: 'bottom-right', lang: 'auto'});
    assertApi('gtmOnFailure').wasCalled();
    assertApi('gtmOnSuccess').wasNotCalled();
setup: ''"""


def loader_url(public_api_url: str) -> str:
    return public_api_url.rstrip("/") + "/widget/loader.js"


def build_template(public_api_url: str) -> str:
    loader = loader_url(public_api_url)
    parts = urlsplit(loader)
    if parts.scheme not in ("http", "https") or not parts.netloc or "'" in loader or "\\" in loader:
        raise ValueError("PUBLIC_API_URL must be an http(s) address")
    info = {
        "type": "TAG",
        "id": "cvt_temp_public_id",
        "version": 1,
        "securityGroups": [],
        "displayName": "FluidBuddha AI agent",
        "categories": ["CHAT", "LEAD_GENERATION", "PERSONALIZATION"],
        "brand": {"id": "brand_fluidbuddha", "displayName": "FluidBuddha"},
        "description": "Adds the FluidBuddha voice and chat agent to your website. "
                       "Paste your widget key from the FluidBuddha console.",
        "containerContexts": ["WEB"],
    }
    permissions = [{
        "instance": {
            "key": {"publicId": "inject_script", "versionId": "1"},
            "param": [{
                "key": "urls",
                "value": {"type": 2, "listItem": [{"type": 1, "string": loader + "*"}]},
            }],
        },
        "clientAnnotations": {"isEditedByUser": True},
        "isRequired": True,
    }]
    sections = [
        ("TERMS_OF_SERVICE", _TERMS),
        ("INFO", json.dumps(info, indent=2)),
        ("TEMPLATE_PARAMETERS", json.dumps(_PARAMETERS, indent=2)),
        ("SANDBOXED_JS_FOR_WEB_TEMPLATE", _CODE.replace("__LOADER__", loader).rstrip()),
        ("WEB_PERMISSIONS", json.dumps(permissions, indent=2)),
        ("TESTS", _TESTS.replace("__LOADER__", loader)),
        ("NOTES", f"Generated by FluidBuddha for {parts.scheme}://{parts.netloc}."),
    ]
    return "".join(f"___{name}___\n\n{body}\n\n\n" for name, body in sections)
