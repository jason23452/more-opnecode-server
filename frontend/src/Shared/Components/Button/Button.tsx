import { Button as HeroButton, type ButtonProps } from '@heroui/react'
import { cn } from '@/Shared/Utils/Cn'

export function Button({ className, ...props }: ButtonProps) {
  return <HeroButton className={cn('font-medium', className)} color="primary" {...props} />
}
