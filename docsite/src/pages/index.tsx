import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <img 
          src="/img/ramalama-logo-full-horiz.svg" 
          alt="RamaLama Logo" 
          className={styles.heroLogo}
        />
        <p className="hero__subtitle">
          Run AI models locally with the simplicity of containers
        </p>
        <div className={styles.buttons}>
          <Link
            className="button button--secondary button--lg"
            to="/docs/getting-started/installation">
            Get Started →
          </Link>
          <Link
            className="button button--outline button--secondary button--lg"
            href="https://matrix.to/#/#ramalama:fedoraproject.org">
            Join Community
          </Link>
        </div>
      </div>
    </header>
  );
}

function HomepageHighlights() {
  return (
    <section className={styles.highlights}>
      <div className="container">
        <div className="row">
          <div className="col col--4">
            <div className="text--center padding-horiz--md">
              <h3>Simple & Familiar</h3>
              <p>
                Use familiar container commands to work with AI models. Pull, run, and serve models just like you would with Docker or Podman.
              </p>
            </div>
          </div>
          <div className="col col--4">
            <div className="text--center padding-horiz--md">
              <h3>Hardware Optimized</h3>
              <p>
                Automatically detects your GPU and pulls optimized container images for NVIDIA, AMD, Intel, Apple Silicon and more.
              </p>
            </div>
          </div>
          <div className="col col--4">
            <div className="text--center padding-horiz--md">
              <h3>Secure by Default</h3>
              <p>
                Run models in rootless containers with read-only mounts, network isolation, and automatic cleanup of temporary data.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function QuickStart() {
  return (
    <section className={styles.quickstart}>
      <div className="container">
        <div className="row">
          <div className="col col--6">
            <Heading as="h2">Quick Start</Heading>
            <p>Install RamaLama and start running AI models in minutes:</p>
            <pre>
              <code>
                # Install via script (Linux/macOS)<br/>
                curl -fsSL https://ramalama.ai/install.sh | bash<br/><br/>
                # Run your first model<br/>
                ramalama run granite3-moe
              </code>
            </pre>
          </div>
          <div className="col col--6">
            <Heading as="h2">Supported Registries</Heading>
            <ul>
              <li>HuggingFace</li>
              <li>ModelScope</li>
              <li>Ollama</li>
              <li>OCI Container Registries (Quay.io, Docker Hub, etc.)</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title} - Run AI Models with Container Simplicity`}
      description="RamaLama makes working with AI simple and straightforward by using OCI containers. Run models locally with automatic hardware optimization and security by default.">
      <HomepageHeader />
      <main>
        <HomepageHighlights />
        <QuickStart />
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
