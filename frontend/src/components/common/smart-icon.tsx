'use client';

import { ComponentType, lazy, Suspense } from 'react';

const iconCache: { [key: string]: ComponentType<any> } = {};

export function SmartIcon({
  name,
  size = 24,
  className,
  ...props
}: {
  name: string;
  size?: number;
  className?: string;
  [key: string]: any;
}) {
  const cacheKey = `lucide-${name}`;

  if (!iconCache[cacheKey]) {
    iconCache[cacheKey] = lazy(async () => {
      try {
        const module = await import('lucide-react');
        const IconComponent = module[name as keyof typeof module];
        if (IconComponent) {
          return { default: IconComponent as ComponentType<any> };
        } else {
          console.warn(
            `Icon "${name}" not found in lucide-react, using fallback`
          );
          return { default: module.HelpCircle as ComponentType<any> };
        }
      } catch (error) {
        console.error(`Failed to load lucide-react:`, error);
        const fallbackModule = await import('lucide-react');
        return { default: fallbackModule.HelpCircle as ComponentType<any> };
      }
    });
  }

  const IconComponent = iconCache[cacheKey];

  return (
    <Suspense fallback={<div style={{ width: size, height: size }} />}>
      <IconComponent size={size} className={className} {...props} />
    </Suspense>
  );
}
