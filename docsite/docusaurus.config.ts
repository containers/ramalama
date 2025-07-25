import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'RamaLama',
  tagline: 'Working with AI made simple, straightforward, and familiar',
  favicon: 'img/favicon.png',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: 'https://ramalama.ai',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/',

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: 'containers', // Usually your GitHub org/user name.
  projectName: 'ramalama', // Usually your repo name.

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: ({ docPath }) =>
            `https://github.com/containers/ramalama/edit/main/docsite/${docPath}`,
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [

  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/logo.svg',
    navbar: {
      title: 'RamaLama',
      logo: {
        alt: 'RamaLama Logo',
        src: 'img/logo.svg',
        srcDark: 'img/logo.svg',
        width: 40,
        height: 40,
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docs',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://blog.ramalama.com',
          label: 'Blog',
          position: 'left',
        },
        {
          href: 'https://github.com/containers/ramalama',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Getting Started',
              to: '/docs/getting-started/installation',
            },
            {
              label: 'API References',
              to: '/docs/commands/ramalama/',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'Issues',
              href: 'https://github.com/containers/ramalama/issues',
            },
            {
              label: 'Matrix',
              href: 'https://matrix.to/#/#ramalama:fedoraproject.org',
            },
            {
              label: 'Discord',
              href: 'https://discord.gg/MkCXuTRBUn',
            },
            {
              label: 'X',
              href: 'https://x.com/RamaLamaLabs',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Blog',
              href: 'https://blog.ramalama.com',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/containers/ramalama',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} RamaLama Contributors.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
