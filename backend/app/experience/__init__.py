"""Generative experience (strategy: docs/product-docs/strategy/GenerativeExperienceStrategy.md).

The Intent → Plan → Bind → Render pipeline. Phase 0 provides:

* ``manifest`` — the component vocabulary a plan may use (the built-in default
  manifest plus an optional per-site customer manifest);
* ``plan`` — the Experience Plan schema (``fb.plan/1``) and its validator;
* ``binding`` — resolves data bindings in a plan from the site's APIs and the
  request context, without the model ever seeing the values;
* ``compose`` — turns a ``generate_page`` tool call into a validated, bound page.
"""
