import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchBar } from '@/components/search/search-bar';

vi.mock('@/lib/api/search', () => ({
  getSuggestions: vi.fn().mockResolvedValue({
    suggestions: [
      { text: 'Wong v Secretary for Justice', type: 'case_name' },
      { text: '[2024] HKCFA 1', type: 'citation' },
      { text: 'Cap. 347', type: 'legislation' },
    ],
  }),
}));

describe('SearchBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders with placeholder text', () => {
    render(<SearchBar />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    expect(input).toBeInTheDocument();
  });

  it('renders with default value', () => {
    render(<SearchBar defaultValue="test query" />);
    
    const input = screen.getByDisplayValue('test query');
    expect(input).toBeInTheDocument();
  });

  it('updates input value on change', async () => {
    const user = userEvent.setup();
    render(<SearchBar />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    await user.type(input, 'contract law');
    
    expect(input).toHaveValue('contract law');
  });

  it('shows clear button when input has value', async () => {
    const user = userEvent.setup();
    render(<SearchBar />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    await user.type(input, 'test');
    
    const clearButton = screen.getByRole('button', { name: '' });
    expect(clearButton).toBeInTheDocument();
  });

  it('clears input when clear button is clicked', async () => {
    const user = userEvent.setup();
    render(<SearchBar defaultValue="test query" />);
    
    const input = screen.getByDisplayValue('test query');
    const clearButton = screen.getAllByRole('button')[0];
    
    await user.click(clearButton);
    
    expect(input).toHaveValue('');
  });

  it('calls onSearch callback when form is submitted', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchBar onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    await user.type(input, 'negligence');
    
    const searchButton = screen.getByRole('button', { name: /search/i });
    await user.click(searchButton);
    
    expect(onSearch).toHaveBeenCalledWith('negligence');
  });

  it('does not submit when input is empty', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchBar onSearch={onSearch} />);
    
    const searchButton = screen.getByRole('button', { name: /search/i });
    expect(searchButton).toBeDisabled();
    
    await user.click(searchButton);
    expect(onSearch).not.toHaveBeenCalled();
  });

  it('renders with large size variant', () => {
    render(<SearchBar size="large" />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    expect(input).toHaveClass('h-14');
  });

  it('auto-focuses input when autoFocus is true', () => {
    render(<SearchBar autoFocus />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    expect(input).toHaveFocus();
  });

  it('fetches suggestions after typing', async () => {
    const { getSuggestions } = await import('@/lib/api/search');
    const user = userEvent.setup();
    render(<SearchBar />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    await user.type(input, 'wong');
    
    await waitFor(() => {
      expect(getSuggestions).toHaveBeenCalledWith('wong');
    }, { timeout: 500 });
  });

  it('handles keyboard navigation in suggestions', async () => {
    const user = userEvent.setup();
    render(<SearchBar />);
    
    const input = screen.getByPlaceholderText(/search cases, legislation/i);
    await user.type(input, 'wong');
    
    await waitFor(() => {
      expect(screen.getByText('Wong v Secretary for Justice')).toBeInTheDocument();
    });
    
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{Escape}');
    
    expect(screen.queryByText('Wong v Secretary for Justice')).not.toBeInTheDocument();
  });
});
