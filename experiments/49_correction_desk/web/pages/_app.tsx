import type { AppProps } from 'next/app';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Noto_Naskh_Arabic } from 'next/font/google';
import { MeProvider } from '../lib/me';
import '../styles/globals.css';

// Arabic content is set in Noto Naskh Arabic, self-hosted by next/font (fetched once at build time).
const naskh = Noto_Naskh_Arabic({ subsets: ['arabic'], weight: ['400', '600'], variable: '--font-naskh', display: 'swap' });

export default function App({ Component, pageProps }: AppProps) {
  const { pathname } = useRouter();
  return (
    <div className={`${naskh.variable} font-sans`}>
      <Head><title>The Desk</title><meta name="robots" content="noindex" /></Head>
      <MeProvider skip={pathname === '/signin'}><Component {...pageProps} /></MeProvider>
    </div>
  );
}
