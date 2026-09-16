---
title: Search
layout: page
---

# Search

## Lexical search

<div id="search"></div>
<link href="/pagefind/pagefind-ui.css" rel="stylesheet">
<script src="/pagefind/pagefind-ui.js"></script>
<script>
  window.addEventListener('DOMContentLoaded', () => {
    new PagefindUI({ element: "#search" });
  });
</script>

## Semantic search

Find papers by meaning rather than exact wording.

<form id="semantic-search-form">
  <input type="text" id="semantic-search-input" placeholder="e.g. ionospheric calibration for wide-field imaging" size="50">
  <button type="submit">Search</button>
</form>
<ul id="semantic-search-results"></ul>

<script src="/assets/js/semantic-search.js"></script>
