---
type: Reference
title: "{{ title }}"
description: "{{ description }}"
resource: "{{ exact_resource_or_source_urn }}"
tags: [image]
status: stable
generated:
  by: "{{ actor }}"
  at: "{{ timestamp }}"
sources:
  - id: "{{ source_id }}"
    resource: "{{ exact_resource_or_source_urn }}"
    title: "{{ title }}"
    content_hash: "{{ source_hash }}"
---

# {{ title }}

![{{ useful_alt_text }}](/assets/sources/{{ source_id }}.png)

## Direct observations

Describe only details visible in the image and cite them.[^{{ source_id }}]

## Machine-extracted text

Check OCR against the image. Record corrections and uncertainty.

## Interpretation and limitations

Separate interpretation from direct observation. Say when visual review was unavailable.

[^{{ source_id }}]: Registered image source `{{ source_id }}`, version `{{ source_hash }}`.
