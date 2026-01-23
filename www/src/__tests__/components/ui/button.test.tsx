import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/ui/button';

describe('Button', () => {
  it('renders with children', () => {
    render(<Button>Click me</Button>);
    
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('applies default variant styles', () => {
    render(<Button>Default</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-primary');
  });

  it('applies destructive variant styles', () => {
    render(<Button variant="destructive">Delete</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-destructive');
  });

  it('applies outline variant styles', () => {
    render(<Button variant="outline">Outline</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('border');
  });

  it('applies ghost variant styles', () => {
    render(<Button variant="ghost">Ghost</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('hover:bg-accent');
  });

  it('applies link variant styles', () => {
    render(<Button variant="link">Link</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('text-primary');
  });

  it('applies small size styles', () => {
    render(<Button size="sm">Small</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('h-8');
  });

  it('applies large size styles', () => {
    render(<Button size="lg">Large</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('h-10');
  });

  it('applies icon size styles', () => {
    render(<Button size="icon">Icon</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('size-9');
  });

  it('handles click events', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);
    
    await user.click(screen.getByRole('button'));
    
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('can be disabled', () => {
    render(<Button disabled>Disabled</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('renders as child component when asChild is true', () => {
    render(
      <Button asChild>
        <a href="/test">Link Button</a>
      </Button>
    );
    
    const link = screen.getByRole('link', { name: /link button/i });
    expect(link).toHaveAttribute('href', '/test');
  });

  it('accepts additional className', () => {
    render(<Button className="custom-class">Custom</Button>);
    
    const button = screen.getByRole('button');
    expect(button).toHaveClass('custom-class');
  });

  it('forwards ref correctly', () => {
    const ref = { current: null };
    render(<Button ref={ref}>Ref Button</Button>);
    
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });
});
