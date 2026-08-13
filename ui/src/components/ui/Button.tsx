import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * NEXARA Button — 石墨为主，金色仅仪式时刻。
 * gold 实底上方必须放石墨文字（#322F2A on #C4A45A = 5.59:1）。
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors duration-[var(--duration-micro)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus-ring)] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-graphite text-ivory hover:bg-[#4A463E] active:bg-[#242119]",
        gold: "bg-champagne text-graphite hover:bg-[#CDB06E] active:bg-[#B89548]",
        ghost:
          "bg-transparent text-graphite border border-border-default hover:bg-surface-hover active:bg-surface-active",
        danger: "bg-danger text-ivory hover:bg-[#9C3D3D] active:bg-[#823232]",
        quiet: "bg-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-9 px-4",
        lg: "h-10 px-5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    isBusy?: boolean;
  };

export function Button({ variant, size, isBusy, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || isBusy}
      aria-busy={isBusy || undefined}
      {...rest}
    >
      {children}
    </button>
  );
}

export { buttonVariants };
