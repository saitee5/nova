import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'nova'
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'md',
  icon,
  className = '',
  disabled,
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-2.5 py-1 text-xs gap-1.5',
    md: 'px-3.5 py-1.5 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  }

  const variantClasses = {
    primary:
      'bg-orange-500 hover:bg-orange-600 text-white font-medium shadow-sm active:translate-y-px border border-orange-600/30',
    secondary:
      'bg-slate-100 hover:bg-slate-200 text-slate-800 font-medium border border-slate-200 shadow-sm',
    outline:
      'bg-white hover:bg-slate-50 text-slate-700 font-medium border border-slate-300 shadow-sm',
    danger:
      'bg-red-600 hover:bg-red-700 text-white font-medium shadow-sm border border-red-700',
    ghost:
      'bg-transparent hover:bg-slate-100 text-slate-600 font-medium',
    nova:
      'bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white font-semibold shadow-md shadow-orange-500/20 active:translate-y-px border border-orange-400/30',
  }

  return (
    <button
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-md font-sans transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
        sizeClasses[size]
      } ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </button>
  )
}
