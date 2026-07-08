'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';

const HeroScene = dynamic(
  () => import('./quantum-scene-inner'),
  { ssr: false }
);

export function QuantumScene({ className }: { className?: string }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
  }

  return (
    <>
      {/* 3D 场景 */}
      <HeroScene className={className} />

      {/* 径向渐变蒙版 - 中心淡化，让文字更清晰 */}
      <div
        className="absolute inset-0 pointer-events-none dark:hidden"
        style={{
          zIndex: 1,
          background: 'radial-gradient(ellipse 80% 50% at 50% 50%, rgba(255, 255, 255, 0.92) 0%, rgba(255, 255, 255, 0.4) 50%, transparent 80%)',
        }}
      />
      <div
        className="absolute inset-0 pointer-events-none hidden dark:block"
        style={{
          zIndex: 1,
          background: 'radial-gradient(ellipse 80% 50% at 50% 50%, rgba(20, 20, 20, 0.92) 0%, rgba(20, 20, 20, 0.4) 50%, transparent 80%)',
        }}
      />
    </>
  );
}

export default QuantumScene;
