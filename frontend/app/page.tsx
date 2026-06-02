import Link from 'next/link';
import Image from 'next/image';

const modules = [
  { n: '01', href: '/dashboard',       label: 'SEO',             desc: 'Productos y rankings' },
  { n: '02', href: '/aeo',             label: 'AEO / GEO',       desc: 'Visibilidad en IA' },
  { n: '03', href: '/solution-engine', label: 'Solution Engine', desc: 'Códigos de falla → producto' },
  { n: '04', href: '/generate',        label: 'Generador',       desc: 'Crear contenido con RAG' },
  { n: '05', href: '/supervisor',      label: 'Supervisor',      desc: 'Noticias y vigilancia IA' },
  { n: '06', href: '/tier-sync',       label: 'B2B Tiers',       desc: 'Sync tags Shopify' },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-v07-surface text-white flex items-center justify-center p-6">
      <div className="text-center w-full">
        <Image
          src="/Logo_Start.png"
          alt=""
          width={128}
          height={64}
          className="h-16 w-auto mx-auto mb-8"
          priority
        />

        <h1 className="text-2xl font-semibold text-white mb-2 tracking-wide">
          SEO PLATFORM
        </h1>
        <p className="text-v07-text-muted text-sm mb-12">
          Sistema Interno de Optimización
        </p>

        <nav aria-label="Módulos principales">
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-v07-header max-w-4xl mx-auto">
            {modules.map((m) => (
              <li key={m.n}>
                <Link
                  href={m.href}
                  className="block bg-v07-surface p-8 hover:bg-v07-card transition-colors group h-full"
                >
                  <div className="text-v07-yellow text-2xl mb-3 font-light">{m.n}</div>
                  <div className="text-white text-sm font-medium mb-1 group-hover:text-v07-yellow transition-colors">
                    {m.label}
                  </div>
                  <div className="text-v07-text-muted text-xs">
                    {m.desc}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="mt-12 text-v07-text-subtle text-xs tracking-widest">
          EXAMPLE STORE © 2026
        </div>
      </div>
    </div>
  );
}
