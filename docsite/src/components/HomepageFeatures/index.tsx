import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  description: ReactNode;
  icon: string;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Multiple Model Support',
    icon: '🤖',
    description: (
      <>
        Run models from HuggingFace, ModelScope, Ollama, and OCI registries. 
        Supports popular formats like GGUF and more.
      </>
    ),
  },
  {
    title: 'REST API & Chat Interface',
    icon: '💬',
    description: (
      <>
        Interact with models through a REST API or use the built-in chat interface.
        Perfect for both application development and direct interaction.
      </>
    ),
  },
  {
    title: 'RAG Support',
    icon: '📚',
    description: (
      <>
        Built-in support for Retrieval Augmented Generation (RAG). Convert your documents
        into vector databases and enhance model responses with your data.
      </>
    ),
  },
  {
    title: 'Cross-Platform',
    icon: '🖥️',
    description: (
      <>
        Works on Linux, macOS, and Windows (via WSL2). Supports both Podman and Docker
        as container engines.
      </>
    ),
  },
  {
    title: 'Performance Benchmarking',
    icon: '📊',
    description: (
      <>
        Built-in tools to benchmark and measure model performance. Calculate perplexity
        and compare different models.
      </>
    ),
  },
  {
    title: 'Active Community',
    icon: '👥',
    description: (
      <>
        Join our active Matrix community for support and discussions. Open source and
        welcoming contributions.
      </>
    ),
  },
];

function Feature({title, description, icon}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <span className={styles.featureIcon}>{icon}</span>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
