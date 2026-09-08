import type { Metadata } from 'next';
import './globals.css';
import Sidebar from './components/Sidebar';
import Header from './components/Header';

export const metadata: Metadata = {
  title: 'Fact Layer',
  description: 'Ingest PDFs, extract atomic facts with verbatim evidence, and reconcile claims.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-surface font-body-md text-body-md text-on-surface antialiased">
        <Sidebar />
        <div className="pl-[220px]">
          <Header />
          <main className="relative pt-14 w-full min-h-screen bg-surface px-space-xl py-space-lg">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
