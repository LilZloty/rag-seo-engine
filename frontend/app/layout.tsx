'use client';

import { Montserrat, JetBrains_Mono } from 'next/font/google';
import { usePathname } from 'next/navigation';
import './globals.css';
import { Providers } from './components/Providers';
import { Header } from './components/layout/Header';
import { useState } from 'react';

const montserrat = Montserrat({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800', '900'],
  variable: '--font-montserrat'
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono'
});

const metadata = {
  title: 'RAG SEO Engine',
  description: 'Generacion de contenido SEO optimizado para productos de transmision',
};

function LayoutContent({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkMode] = useState(true);
  const pathname = usePathname();
  const isSplash = pathname === '/';

  return (
    <div className="min-h-screen bg-v07-surface">
      {!isSplash && (
        <Header
          title="Example Store"
          subtitle="SEO Engine"
          darkMode={darkMode}
          onToggleTheme={() => setDarkMode(!darkMode)}
        />
      )}
      <main>
        {children}
      </main>
    </div>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      {/* suppressHydrationWarning on <body> only — Grammarly, ColorZilla and similar
          extensions inject attributes (data-gr-ext-installed, cz-shortcut-listen, etc.)
          before React hydrates, producing a hydration mismatch that isn't a real bug. */}
      <body
        className={`${montserrat.className} ${jetbrainsMono.variable}`}
        suppressHydrationWarning
      >
        <Providers>
          <LayoutContent>
            {children}
          </LayoutContent>
        </Providers>
      </body>
    </html>
  );
}

