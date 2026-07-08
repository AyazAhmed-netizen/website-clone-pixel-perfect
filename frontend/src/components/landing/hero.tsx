"use client";

import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Github } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollAnimation } from "@/components/ui/scroll-animation";
import { cn } from "@/lib/utils";

interface HeroProps {
  title: string;
  highlightText?: string;
  description: string;
  announcement?: {
    title: string;
    url: string;
  };
  buttons?: Array<{
    title: string;
    url: string;
    variant?: "default" | "outline";
    icon?: string;
  }>;
  image?: {
    src: string;
    alt: string;
  };
  className?: string;
}

export function Hero({
  title,
  highlightText,
  description,
  announcement,
  buttons,
  image,
  className,
}: HeroProps) {
  let texts: string[] | null = null;
  if (highlightText) {
    texts = title.split(highlightText, 2);
  }

  return (
    <section className={cn("pt-24 pb-8 md:pt-36 md:pb-8", className)}>
      {announcement && (
        <ScrollAnimation>
          <Link
            href={announcement.url}
            className="hover:bg-background dark:hover:border-t-border bg-muted group mx-auto mb-8 flex w-fit items-center gap-4 rounded-full border p-1 pl-4 shadow-md shadow-zinc-950/5 transition-colors duration-300 dark:border-t-white/5 dark:shadow-zinc-950"
          >
            <span className="text-foreground text-sm">{announcement.title}</span>
            <span className="dark:border-background block h-4 w-0.5 border-l bg-white dark:bg-zinc-700" />
            <div className="bg-background group-hover:bg-muted size-6 overflow-hidden rounded-full duration-500">
              <div className="flex w-12 -translate-x-1/2 duration-500 ease-in-out group-hover:translate-x-0">
                <span className="flex size-6">
                  <ArrowRight className="m-auto size-3" />
                </span>
                <span className="flex size-6">
                  <ArrowRight className="m-auto size-3" />
                </span>
              </div>
            </div>
          </Link>
        </ScrollAnimation>
      )}

      <div className="relative mx-auto max-w-full px-4 text-center md:max-w-5xl">
        <ScrollAnimation delay={0.1}>
          {texts && texts.length > 0 ? (
            <h1 className="text-foreground text-4xl font-semibold text-balance sm:mt-12 sm:text-6xl">
              {texts[0]}
              <span className="relative inline-block">
                <span className="relative z-10">{highlightText}</span>
                <span className="absolute bottom-1 left-0 right-0 h-3 bg-primary/30 -rotate-1" />
              </span>
              {texts[1]}
            </h1>
          ) : (
            <h1 className="text-foreground text-4xl font-semibold text-balance sm:mt-12 sm:text-6xl">
              {title}
            </h1>
          )}
        </ScrollAnimation>

        <ScrollAnimation delay={0.2}>
          <p
            className="text-muted-foreground mt-8 mb-8 text-lg text-balance"
            dangerouslySetInnerHTML={{ __html: description }}
          />
        </ScrollAnimation>

        {buttons && buttons.length > 0 && (
          <ScrollAnimation delay={0.3}>
            <div className="flex items-center justify-center gap-4">
              {buttons.map((button, idx) => (
                <Button
                  asChild
                  variant={button.variant || "default"}
                  className="px-4 text-sm"
                  key={idx}
                >
                  <Link href={button.url}>
                    {button.icon === "Github" && <Github className="mr-2 h-4 w-4" />}
                    <span>{button.title}</span>
                  </Link>
                </Button>
              ))}
            </div>
          </ScrollAnimation>
        )}
      </div>

      {image?.src && (
        <ScrollAnimation delay={0.4}>
          <div className="border-foreground/10 relative mt-8 border-y sm:mt-16">
            <div className="relative z-10 mx-auto max-w-6xl border-x px-3">
              <div className="border-x">
                <div
                  aria-hidden
                  className="h-3 w-full bg-[repeating-linear-gradient(-45deg,var(--color-foreground),var(--color-foreground)_1px,transparent_1px,transparent_4px)] opacity-5"
                />
                <Image
                  className="border-border/25 relative z-2 w-full border"
                  src={image.src}
                  alt={image.alt}
                  width={1200}
                  height={630}
                  sizes="(max-width: 768px) 100vw, 1200px"
                  loading="lazy"
                  quality={75}
                />
              </div>
            </div>
          </div>
        </ScrollAnimation>
      )}
    </section>
  );
}
