import { forwardRef } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97]',
  {
    variants: {
      variant: {
        default:
          'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:brightness-110 shadow-sm',
        destructive:
          'bg-[hsl(var(--destructive))] text-white hover:brightness-110 shadow-sm',
        outline:
          'glass-input bg-[var(--glass-bg)] text-[hsl(var(--foreground))] hover:bg-[var(--glass-bg-heavy)]',
        secondary:
          'bg-[hsl(var(--secondary))] text-[hsl(var(--secondary-foreground))] hover:brightness-95',
        ghost:
          'text-[hsl(var(--muted-foreground))] hover:bg-[var(--input-bg)] hover:text-[hsl(var(--foreground))]',
        link:
          'text-[hsl(var(--primary))] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-5 py-2',
        sm: 'h-8 rounded-lg px-3 text-xs',
        lg: 'h-12 rounded-xl px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

const Button = forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  )
})
Button.displayName = 'Button'

export { Button, buttonVariants }
