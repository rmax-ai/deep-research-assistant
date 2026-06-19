<script>
  import { base } from "$app/paths";

  let { children } = $props();
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<div class="app">
  <nav class="top-nav">
    <a href={base + "/"} class="logo">Deep Research</a>
    <div class="nav-links">
      <a href={base + "/architecture/"}>Architecture</a>
      <a href={base + "/phases/"}>Phases</a>
      <a href={base + "/api/"}>API</a>
      <a href="https://github.com/rmax-ai/deep-research-assistant" class="gh-link">GitHub ↗</a>
    </div>
  </nav>
  <main>{@render children()}</main>
  <footer>
    <p>Deep Research Assistant · MIT License · Built with ADK 2.0 + SvelteKit</p>
  </footer>
</div>

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(body) {
    font-family: "Inter", system-ui, sans-serif;
    background: #020617;
    color: #e2e8f0;
    line-height: 1.6;
    min-height: 100vh;
  }

  :global(h1, h2, h3, h4, h5, h6) {
    font-family: "JetBrains Mono", monospace;
    font-weight: 600;
  }

  :global(code) {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.875em;
    background: rgba(30, 41, 59, 0.5);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    color: #22d3ee;
  }

  :global(pre) {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin: 1rem 0;
  }

  :global(pre code) {
    background: none;
    padding: 0;
    color: #e2e8f0;
  }

  :global(a) {
    color: #22d3ee;
    text-decoration: none;
  }

  :global(a:hover) {
    text-decoration: underline;
  }

  :global(ul, ol) {
    padding-left: 1.5rem;
    margin: 0.5rem 0;
  }

  :global(li) {
    margin: 0.25rem 0;
  }

  :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
  }

  :global(th) {
    text-align: left;
    background: rgba(30, 41, 59, 0.5);
    padding: 0.5rem 1rem;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.8rem;
    color: #94a3b8;
    border-bottom: 1px solid #334155;
  }

  :global(td) {
    padding: 0.5rem 1rem;
    border-bottom: 1px solid #1e293b;
    font-size: 0.875rem;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 2rem;
    border-bottom: 1px solid #1e293b;
    background: rgba(2, 6, 23, 0.9);
    backdrop-filter: blur(12px);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .logo {
    font-family: "JetBrains Mono", monospace;
    font-weight: 700;
    font-size: 1.1rem;
    color: #22d3ee !important;
    text-decoration: none !important;
  }

  .nav-links {
    display: flex;
    gap: 1.5rem;
    align-items: center;
  }

  .nav-links a {
    font-size: 0.875rem;
    font-weight: 500;
    color: #94a3b8;
    text-decoration: none;
    transition: color 0.15s;
  }

  .nav-links a:hover {
    color: #e2e8f0;
    text-decoration: none;
  }

  .gh-link {
    color: #22d3ee !important;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.8rem;
  }

  main {
    flex: 1;
  }

  footer {
    text-align: center;
    padding: 2rem;
    font-size: 0.75rem;
    color: #475569;
    border-top: 1px solid #1e293b;
    font-family: "JetBrains Mono", monospace;
  }
</style>
