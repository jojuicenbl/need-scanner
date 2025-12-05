import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { cn } from "@/lib/utils";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "unmet - Surface unmet needs",
    description: "Surface unmet needs. Build what matters.",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body
                className={cn(inter.className, "bg-slate-50 text-slate-900 min-h-screen")}
                suppressHydrationWarning
            >
                <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Link href="/" className="text-xl font-bold tracking-tight text-slate-900">
                                unmet
                            </Link>
                            <div className="hidden md:block h-4 w-px bg-slate-200" />
                            <p className="hidden md:block text-sm text-slate-500 font-medium">
                                Surface unmet needs. Build what matters.
                            </p>
                        </div>
                        <nav className="flex items-center gap-6">
                            <Link href="/runs" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
                                Runs
                            </Link>
                            <Link
                                href="/"
                                className="text-sm font-medium bg-slate-900 text-white px-4 py-2 rounded-md hover:bg-slate-800 transition-colors"
                            >
                                New Scan
                            </Link>
                        </nav>
                    </div>
                </header>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    {children}
                </main>
            </body>
        </html>
    );
}
