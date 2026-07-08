"use client";

import Image from "next/image";
import {
  ImageOff,
  CheckCircle,
  X,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

const iconMap: Record<string, LucideIcon> = {
  ImageOff,
  CheckCircle,
  X,
  Sparkles,
};

interface FeaturesListProps {
  id?: string;
  label?: string;
  title: string;
  description: string;
  image?: {
    src: string;
    alt: string;
  };
  items: Array<{
    title: string;
    description: string;
    icon: string;
  }>;
  className?: string;
}

export function FeaturesList({
  id,
  label,
  title,
  description,
  image,
  items,
  className,
}: FeaturesListProps) {
  return (
    <section
      id={id}
      className={cn("overflow-x-hidden py-16 md:py-24", className)}
    >
      <div className="container overflow-x-hidden">
        <div className="flex flex-wrap items-center gap-8 pb-12 md:gap-24">
          <ScrollAnimation direction="left">
            <div className="mx-auto w-full max-w-[500px] flex-shrink-0 md:mx-0">
              {image?.src && (
                <Image
                  src={image.src}
                  alt={image.alt}
                  width={500}
                  height={350}
                  className="h-auto w-full rounded-lg object-cover"
                />
              )}
            </div>
          </ScrollAnimation>

          <div className="w-full min-w-0 flex-1">
            <ScrollAnimation delay={0.1}>
              {label && (
                <span className="text-primary text-sm font-medium mb-2 block">
                  {label}
                </span>
              )}
              <h2 className="text-foreground text-4xl font-semibold text-balance break-words">
                {title}
              </h2>
            </ScrollAnimation>
            <ScrollAnimation delay={0.2}>
              <p className="text-md text-muted-foreground my-6 text-balance break-words">
                {description}
              </p>
            </ScrollAnimation>
          </div>
        </div>

        <ScrollAnimation delay={0.1}>
          <div className="relative grid min-w-0 grid-cols-1 gap-x-3 gap-y-6 border-t pt-12 break-words sm:grid-cols-2 sm:gap-6 lg:grid-cols-4">
            {items.map((item, idx) => {
              const Icon = iconMap[item.icon] || Sparkles;
              return (
                <div className="min-w-0 space-y-3 break-words" key={idx}>
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <h3 className="min-w-0 text-sm font-medium break-words">
                      {item.title}
                    </h3>
                  </div>
                  <p className="text-muted-foreground min-w-0 text-sm break-words">
                    {item.description}
                  </p>
                </div>
              );
            })}
          </div>
        </ScrollAnimation>
      </div>
    </section>
  );
}
