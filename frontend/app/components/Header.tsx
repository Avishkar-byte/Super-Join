export default function Header() {
  return (
    <header className="fixed top-0 left-[220px] right-0 h-14 bg-surface/90 backdrop-blur-md border-b border-surface-container z-20 flex items-center justify-between px-space-xl">
      <div className="flex items-center gap-space-sm">
        <span className="material-symbols-outlined text-[16px] text-outline">terminal</span>
        <span className="font-label-code-sm text-label-code-sm text-on-surface-variant">audit://engine.v1.prd</span>
      </div>

    </header>
  );
}
