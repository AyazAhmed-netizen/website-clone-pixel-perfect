"use client";

import Image from "next/image";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

interface LogosProps {
  title: string;
  items: Array<{
    title: string;
    image: {
      src: string;
      alt: string;
    };
  }>;
  className?: string;
}

export function Logos({ title, items, className }: LogosProps) {
  return (
    <section className={cn("py-16 md:py-24", className)}>
      <div className="mx-auto max-w-5xl px-6">
        <ScrollAnimation>
          <p className="text-md text-center font-medium">{title}</p>
        </ScrollAnimation>
        <ScrollAnimation delay={0.2}>
          <div className="mx-auto mt-12 flex max-w-4xl flex-wrap items-center justify-center gap-x-12 gap-y-8 sm:gap-x-16 sm:gap-y-12">
            {items.map((item, idx) => (
              <Image
                key={idx}
                className="h-8 w-auto dark:invert"
                src={item.image.src}
                alt={item.image.alt}
                width={120}
                height={32}
              />
            ))}
          </div>
        </ScrollAnimation>
      </div>
    </section>
  );
}
