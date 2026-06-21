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
    font-size: clamp(2.4rem, 5vw, 4rem);
    margin-bottom: 0.8rem;
    color: var(--text-strong);
    letter-spacing: -0.02em;
  }

  :global(.doc h2) {
    font-size: 1.5rem;
    margin-top: 2.5rem;
    margin-bottom: 0.75rem;
    color: var(--text-strong);
    border-bottom: 1px solid var(--line);
    padding-bottom: 0.35rem;
  }

  :global(.doc h3) {
    font-size: 1.1rem;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    color: #28415c;
  }

  :global(.doc p) {
    margin: 0.75rem 0;
    color: var(--text-body);
  }

  :global(.doc strong) {
    color: var(--text-strong);
  }

  :global(.doc blockquote) {
    border-left: 3px solid var(--accent);
    padding-left: 1rem;
    margin: 1rem 0;
    color: var(--text-soft);
    font-style: italic;
    font-family: "Instrument Serif", serif;
    font-size: 1.2rem;
  }

  :global(.doc hr) {
    border: none;
    border-top: 1px solid var(--line);
    margin: 2rem 0;
  }
</style>
