import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CaseHeader } from '@/components/cases/case-header';
import type { CaseDetail } from '@/types';

vi.mock('@/components/collections', () => ({
  AddToCollectionButton: () => (
    <button data-testid="add-to-collection">Add to collection</button>
  ),
}));

const mockCase: CaseDetail = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  neutral_citation: '[2024] HKCFA 1',
  case_name: 'Wong v Secretary for Justice',
  court: {
    id: 'court-1',
    name_en: 'Court of Final Appeal',
    code: 'CFA',
  },
  decision_date: '2024-01-15',
  judges: ['Chief Justice Cheung', 'Mr Justice Ribeiro PJ'],
  headnote: 'Test headnote',
  pdf_url: 'https://example.com/case.pdf',
};

describe('CaseHeader', () => {
  let clipboardWriteTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();

    clipboardWriteTextMock = vi.fn().mockResolvedValue(undefined);

    const stubNavigator = {
      ...window.navigator,
      share: undefined,
      clipboard: {
        writeText: clipboardWriteTextMock,
      },
    } as unknown as Navigator;

    vi.stubGlobal('navigator', stubNavigator);

    Object.defineProperty(window, 'navigator', {
      configurable: true,
      value: stubNavigator,
    });
  });

  it('renders case name', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByRole('heading', { name: 'Wong v Secretary for Justice' })).toBeInTheDocument();
  });

  it('renders neutral citation', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByText('[2024] HKCFA 1')).toBeInTheDocument();
  });

  it('renders court name', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByText('Court of Final Appeal')).toBeInTheDocument();
  });

  it('renders formatted decision date', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByText('15 January 2024')).toBeInTheDocument();
  });

  it('renders judges as badges', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByText('Chief Justice Cheung')).toBeInTheDocument();
    expect(screen.getByText('Mr Justice Ribeiro PJ')).toBeInTheDocument();
  });

  it('renders PDF download link when pdf_url is present', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    const pdfLink = screen.getByRole('link');
    expect(pdfLink).toHaveAttribute('href', 'https://example.com/case.pdf');
    expect(pdfLink).toHaveAttribute('target', '_blank');
  });

  it('does not render PDF button when pdf_url is absent', () => {
    const caseWithoutPdf = { ...mockCase, pdf_url: undefined };
    render(<CaseHeader caseData={caseWithoutPdf} />);
    
    expect(screen.queryByText('PDF')).not.toBeInTheDocument();
  });

  it('renders share button', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByRole('button', { name: /share/i })).toBeInTheDocument();
  });

  it('handles share click when navigator.share is unavailable', async () => {
    const user = userEvent.setup();
    render(<CaseHeader caseData={mockCase} />);

    expect(navigator.share).toBeUndefined();
    
    const shareButton = screen.getByRole('button', { name: /share/i });
    await expect(user.click(shareButton)).resolves.toBeUndefined();
  });

  it('renders AddToCollectionButton', () => {
    render(<CaseHeader caseData={mockCase} />);
    
    expect(screen.getByTestId('add-to-collection')).toBeInTheDocument();
  });

  it('does not render judges section when judges array is empty', () => {
    const caseWithoutJudges = { ...mockCase, judges: [] };
    render(<CaseHeader caseData={caseWithoutJudges} />);
    
    expect(screen.queryByText('Judges:')).not.toBeInTheDocument();
  });

  it('does not render court when court is undefined', () => {
    const caseWithoutCourt = { ...mockCase, court: undefined } as unknown as CaseDetail;
    render(<CaseHeader caseData={caseWithoutCourt} />);
    
    expect(screen.queryByText('Court of Final Appeal')).not.toBeInTheDocument();
  });
});
