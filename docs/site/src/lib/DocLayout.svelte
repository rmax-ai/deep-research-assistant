<script>
  let { children } = $props();
</script>

<article class="doc">
  {@render children()}
</article>

<style>
  .doc {
    max-width: 820px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }

  :global(.doc h1) {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    color: #f1f5f9;
    letter-spacing: -0.02em;
  }

  :global(.doc h2) {
    font-size: 1.35rem;
    margin-top: 2.5rem;
    margin-bottom: 0.75rem;
    color: #e2e8f0;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 0.35rem;
  }

  :global(.doc h3) {
    font-size: 1.1rem;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    color: #cbd5e1;
  }

  :global(.doc p) {
    margin: 0.75rem 0;
    color: #94a3b8;
  }

  :global(.doc strong) {
    color: #e2e8f0;
  }

  :global(.doc blockquote) {
    border-left: 3px solid #22d3ee;
    padding-left: 1rem;
    margin: 1rem 0;
    color: #64748b;
    font-style: italic;
  }

  :global(.doc hr) {
    border: none;
    border-top: 1px solid #1e293b;
    margin: 2rem 0;
  }
</style>
