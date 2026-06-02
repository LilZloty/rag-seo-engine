'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { SunIcon, MoonIcon } from '../ui/Icons';
import { LLMProviderSelector } from '../LLMProviderSelector';

interface HeaderProps {
    title: string;
    subtitle?: string;
    darkMode: boolean;
    onToggleTheme: () => void;
    actions?: React.ReactNode;
    showBackLink?: boolean;
    backHref?: string;
    backLabel?: string;
}

const BRAND_YELLOW = '#f7b500';

const navItems = [
    { href: '/', label: 'Inicio' },
    {
        href: '/intelligence',
        label: 'Ecommerce',
        highlight: true,
        children: [
            { href: '/intelligence', label: 'Intelligence' },
            { href: '/intelligence/opportunities', label: 'Opportunities' },
            { href: '/intelligence/sucursales', label: 'Sucursales' },
            { href: '/inventory', label: 'Inventory' },
            { href: '/solution-engine', label: 'Solution Engine' },
            { href: '/creative-intelligence', label: 'Creative Ads' },
        ]
    },
    { href: '/aeo', label: 'AEO / GEO' },
    {
        href: '/seo/dashboard',
        label: 'SEO',
        children: [
            { href: '/seo/dashboard', label: 'Dashboard SEO' },
            { href: '/seo/intelligence', label: 'SEO Intelligence' },
            { href: '/seo/dashboard?tab=collections', label: 'Collections' },
            { href: '/seo/articles', label: 'Articles' },
            { href: '/libraries', label: 'Librerías' },
        ]
    },
    { href: '/supervisor', label: 'Supervisor' },
    { href: '/tier-sync', label: 'B2B Tiers' },
];

/**
 * Header - Clean Minimal Design
 * 
 * Design Philosophy:
 * - No background containers
 * - Clean floating elements
 * - Visual hierarchy through typography and spacing
 * - Sharp angles, no rounded corners
 * - Minimal visual noise
 */
export function Header({
    title,
    subtitle,
    darkMode,
    onToggleTheme,
    actions,
    showBackLink = false,
    backHref = '/',
    backLabel = 'Volver',
}: HeaderProps) {
    const pathname = usePathname();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [openDropdown, setOpenDropdown] = useState<string | null>(null);

    return (
        <>
            <header className="relative h-16 bg-[#0a0a0a] sticky top-0 z-50">
                <div className="size-full px-4 sm:px-6 lg:px-10 flex items-center gap-4">

                    {/* LEFT: Logo + Title — fixed width, won't shrink */}
                    <div className="flex items-center gap-4 flex-shrink-0">
                        {showBackLink ? (
                            <Link
                                href={backHref}
                                className="flex items-center gap-2 text-[#999999] hover:text-white transition-colors duration-200"
                            >
                                <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 19l-7-7 7-7" />
                                </svg>
                                <span className="hidden sm:inline text-sm font-medium">{backLabel}</span>
                            </Link>
                        ) : (
                            <Link href="/" className="flex items-center">
                                <Image src="/Logo_Start.png" alt="Example Store" width={80} height={40} className="h-10 w-auto" priority />
                            </Link>
                        )}

                        <div className="hidden md:block">
                            <h1 className="text-sm font-semibold text-white tracking-wide">{title}</h1>
                            {subtitle && <p className="text-xs text-[#888888] mt-0.5">{subtitle}</p>}
                        </div>
                    </div>

                    {/* CENTER: Navigation — centered, equal gap between all items */}
                    <nav className="hidden lg:flex items-center justify-center flex-1 min-w-0">
                        <div className="flex items-center gap-6 xl:gap-8">
                            {navItems.map((item) => {
                                const isActive = pathname === item.href ||
                                    (item.href !== '/' && pathname?.startsWith(item.href));
                                const hasChildren = item.children && item.children.length > 0;

                                if (hasChildren) {
                                    return (
                                        <div
                                            key={item.href}
                                            className="relative z-50"
                                        >
                                            <button
                                                onMouseEnter={() => setOpenDropdown(item.href)}
                                                onClick={() => setOpenDropdown(openDropdown === item.href ? null : item.href)}
                                                className={`
                                                    py-2 text-sm font-medium whitespace-nowrap
                                                    transition-all duration-200 flex items-center gap-1
                                                    ${isActive
                                                        ? 'text-[#f7b500]'
                                                        : item.highlight
                                                            ? 'text-[#f7b500] hover:text-[#ffc933]'
                                                            : 'text-[#999999] hover:text-white'
                                                    }
                                                `}
                                            >
                                                <span className="relative">
                                                    {item.label}
                                                    {isActive && (
                                                        <span className="absolute -bottom-1 left-0 right-0 h-px bg-[#f7b500]" />
                                                    )}
                                                </span>
                                                <svg className="size-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                </svg>
                                            </button>

                                            {/* Dropdown Menu */}
                                            <div
                                                className={`
                                                    absolute top-full left-1/2 -translate-x-1/2 mt-1 w-48 bg-[#0a0a0a] border border-[#f7b500]/30
                                                    transition-all duration-200 origin-top z-50
                                                    ${openDropdown === item.href ? 'opacity-100 scale-y-100' : 'opacity-0 scale-y-0 pointer-events-none'}
                                                `}
                                                onMouseLeave={() => setOpenDropdown(null)}
                                            >
                                                {item.children.map((child) => {
                                                    const isChildActive = pathname === child.href ||
                                                        pathname?.startsWith(child.href);
                                                    return (
                                                        <Link
                                                            key={child.href}
                                                            href={child.href}
                                                            onClick={() => setOpenDropdown(null)}
                                                            className={`
                                                                block px-4 py-3 text-sm transition-all duration-200
                                                                ${isChildActive
                                                                    ? 'text-[#f7b500] bg-[#f7b500]/10'
                                                                    : 'text-[#999999] hover:text-white hover:bg-[#1a1a1a]'
                                                                }
                                                            `}
                                                        >
                                                            {child.label}
                                                        </Link>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    );
                                }

                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        className={`
                                            py-2 text-sm font-medium whitespace-nowrap
                                            transition-all duration-200
                                            ${isActive
                                                ? 'text-[#f7b500]'
                                                : item.highlight
                                                    ? 'text-[#f7b500] hover:text-[#ffc933]'
                                                    : 'text-[#999999] hover:text-white'
                                            }
                                        `}
                                    >
                                        <span className="relative">
                                            {item.label}
                                            {isActive && (
                                                <span className="absolute -bottom-1 left-0 right-0 h-px bg-[#f7b500]" />
                                            )}
                                        </span>
                                    </Link>
                                );
                            })}
                        </div>
                    </nav>

                    {/* RIGHT: Actions — fixed width, won't shrink */}
                    <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="hidden sm:flex items-center">
                            <LLMProviderSelector />
                        </div>

                        <button
                            onClick={onToggleTheme}
                            className={`
                                size-9 flex items-center justify-center
                                text-[#999999] hover:text-[#f7b500]
                                transition-all duration-200
                                ${darkMode ? 'text-[#f7b500]' : ''}
                            `}
                            aria-label={darkMode ? 'Modo claro' : 'Modo oscuro'}
                        >
                            {darkMode ? <SunIcon size={18} /> : <MoonIcon size={18} />}
                        </button>

                        {actions && (
                            <div className="flex items-center flex-shrink-0">
                                {actions}
                            </div>
                        )}

                        {/* Mobile Menu Toggle */}
                        <button
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            className={`
                                lg:hidden size-9 flex items-center justify-center
                                transition-all duration-200
                                ${mobileMenuOpen ? 'text-[#f7b500]' : 'text-[#999999] hover:text-white'}
                            `}
                            aria-label="Menú"
                        >
                            <div className="relative w-5 h-4">
                                <span className={`absolute left-0 block w-5 h-0.5 bg-current transition-all duration-200 ${mobileMenuOpen ? 'top-2 rotate-45' : 'top-0'}`} />
                                <span className={`absolute left-0 top-2 block w-5 h-0.5 bg-current transition-all duration-200 ${mobileMenuOpen ? 'opacity-0' : 'opacity-100'}`} />
                                <span className={`absolute left-0 block w-5 h-0.5 bg-current transition-all duration-200 ${mobileMenuOpen ? 'top-2 -rotate-45' : 'top-4'}`} />
                            </div>
                        </button>
                    </div>
                </div>

                {/* Bottom accent line */}
                <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#f7b500]/30 to-transparent" />
            </header>

            {/* Mobile Menu */}
            <div
                className={`
                    lg:hidden fixed inset-x-0 top-16 z-40 bg-[#0a0a0a] border-b border-[#f7b500]/30
                    transition-all duration-300 ease-out
                    ${mobileMenuOpen ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4 pointer-events-none'}
                `}
            >
                <nav className="py-4 px-6 space-y-1">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href ||
                            (item.href !== '/' && pathname?.startsWith(item.href));
                        const hasChildren = item.children && item.children.length > 0;

                        if (hasChildren) {
                            return (
                                <div key={item.href} className="space-y-1">
                                    <div className="py-3 text-base font-medium text-[#f7b500]">
                                        {item.label}
                                    </div>
                                    <div className="pl-4 space-y-1 border-l-2 border-[#f7b500]/30">
                                        {item.children.map((child) => {
                                            const isChildActive = pathname === child.href ||
                                                pathname?.startsWith(child.href);
                                            return (
                                                <Link
                                                    key={child.href}
                                                    href={child.href}
                                                    onClick={() => setMobileMenuOpen(false)}
                                                    className={`
                                                        block py-2 text-sm font-medium
                                                        transition-all duration-200
                                                        ${isChildActive
                                                            ? 'text-[#f7b500]'
                                                            : 'text-[#999999] hover:text-white'
                                                        }
                                                    `}
                                                >
                                                    {child.label}
                                                </Link>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        }

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={() => setMobileMenuOpen(false)}
                                className={`
                                    block py-3 text-base font-medium
                                    transition-all duration-200
                                    ${isActive
                                        ? 'text-[#f7b500]'
                                        : item.highlight
                                            ? 'text-[#f7b500] hover:text-[#ffc933]'
                                            : 'text-[#999999] hover:text-white'
                                    }
                                `}
                            >
                                {item.label}
                            </Link>
                        );
                    })}

                    <div className="pt-4 mt-4 border-t border-[#1a1a1a]">
                        <p className="text-xs text-[#888888] uppercase tracking-wider mb-3">Proveedor IA</p>
                        <LLMProviderSelector />
                    </div>
                </nav>
            </div>

            {mobileMenuOpen && (
                <div
                    className="lg:hidden fixed inset-0 top-16 bg-black/50 z-30"
                    role="presentation"
                    onClick={() => setMobileMenuOpen(false)}
                    onKeyDown={(e) => { if (e.key === 'Escape') setMobileMenuOpen(false); }}
                />
            )}
        </>
    );
}

// Header is exported as named export only
