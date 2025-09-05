import { InputHTMLAttributes, forwardRef } from 'react';
import { clsx } from 'clsx';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  variant?: 'default' | 'outline' | 'filled';
  inputSize?: 'sm' | 'md' | 'lg';
  error?: boolean;
  helperText?: string;
  label?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(({
  className,
  variant = 'default',
  inputSize = 'md',
  error = false,
  helperText,
  label,
  ...props
}, ref) => {
  const baseClasses = 'block w-full rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-0';
  
  const variantClasses = {
    default: 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
    outline: 'border-gray-300 bg-transparent focus:border-blue-500 focus:ring-blue-500',
    filled: 'border-gray-200 bg-gray-50 focus:border-blue-500 focus:ring-blue-500',
  };
  
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-4 py-3 text-base',
  };
  
  const errorClasses = error 
    ? 'border-red-300 focus:border-red-500 focus:ring-red-500' 
    : '';

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <input
        ref={ref}
        className={clsx(
          baseClasses,
          variantClasses[variant],
          sizeClasses[inputSize],
          errorClasses,
          className
        )}
        {...props}
      />
      {helperText && (
        <p className={clsx(
          'mt-1 text-xs',
          error ? 'text-red-600' : 'text-gray-500'
        )}>
          {helperText}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;