import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// GitHub Pages serves this at https://giovi321.github.io/plaud-unofficial-api/
export default defineConfig({
  site: 'https://giovi321.github.io',
  base: '/plaud-unofficial-api',
  integrations: [
    starlight({
      title: 'Plaud CLI',
      description: 'Unofficial command-line tool for the Plaud.ai API',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/giovi321/plaud-unofficial-api' },
      ],
      editLink: { baseUrl: 'https://github.com/giovi321/plaud-unofficial-api/edit/main/docs/' },
      sidebar: [
        { label: 'Home', link: '/' },
        {
          label: 'Getting started',
          items: [
            { label: 'Installation', link: '/getting-started/installation/' },
            { label: 'Authentication', link: '/getting-started/authentication/' },
            { label: 'Configuration', link: '/getting-started/configuration/' },
          ],
        },
        {
          label: 'Commands',
          items: [
            { label: 'list', link: '/commands/list/' },
            { label: 'detail', link: '/commands/detail/' },
            { label: 'export', link: '/commands/export/' },
            { label: 'sync', link: '/commands/sync/' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Sync readiness', link: '/guides/readiness/' },
            { label: 'Content extraction', link: '/guides/extraction/' },
          ],
        },
        {
          label: 'Development',
          items: [
            { label: 'Contributing', link: '/development/contributing/' },
          ],
        },
      ],
    }),
  ],
});
