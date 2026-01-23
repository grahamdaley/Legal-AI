import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { search, getSuggestions, getCaseDetail, getLegislationDetail, getCaseCitations } from '@/lib/api/search';

const mockFetch = vi.fn();
global.fetch = mockFetch;

vi.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: 'test-token' } },
      }),
    },
  }),
}));

describe('Search API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('search', () => {
    it('sends POST request with correct body', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          results: [],
          query: 'test',
          searchMode: 'hybrid',
          type: 'all',
          timing: { embedding_ms: 10, search_ms: 20, total_ms: 30 },
        }),
      });

      const request = { query: 'test query', type: 'cases' as const };
      await search(request);

      expect(mockFetch).toHaveBeenCalledWith('/api/search', {
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify(request),
      });
    });

    it('includes authorization header when authenticated', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: [], query: 'test', searchMode: 'hybrid', type: 'all', timing: {} }),
      });

      await search({ query: 'test' });

      expect(mockFetch).toHaveBeenCalledWith('/api/search', expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer test-token',
        }),
      }));
    });

    it('throws error on failed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'Search failed' } }),
      });

      await expect(search({ query: 'test' })).rejects.toThrow('Search failed');
    });

    it('returns search response on success', async () => {
      const mockResponse = {
        results: [{ id: '1', case_name: 'Test Case' }],
        query: 'test',
        searchMode: 'hybrid',
        type: 'cases',
        timing: { embedding_ms: 10, search_ms: 20, total_ms: 30 },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await search({ query: 'test' });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getSuggestions', () => {
    it('sends GET request with query parameter', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ suggestions: [] }),
      });

      await getSuggestions('wong');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/suggestions?q=wong',
        expect.objectContaining({ headers: expect.any(Object) })
      );
    });

    it('includes type parameter when provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ suggestions: [] }),
      });

      await getSuggestions('wong', 'cases');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/suggestions?q=wong&type=cases',
        expect.any(Object)
      );
    });

    it('returns suggestions on success', async () => {
      const mockSuggestions = {
        suggestions: [
          { text: 'Wong v Secretary', type: 'case_name' },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSuggestions),
      });

      const result = await getSuggestions('wong');
      expect(result).toEqual(mockSuggestions);
    });

    it('throws error on failed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'Failed to get suggestions' } }),
      });

      await expect(getSuggestions('test')).rejects.toThrow('Failed to get suggestions');
    });
  });

  describe('getCaseDetail', () => {
    it('sends GET request with case ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: '123', case_name: 'Test' }),
      });

      await getCaseDetail('123');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/cases/123',
        expect.objectContaining({ headers: expect.any(Object) })
      );
    });

    it('returns case detail on success', async () => {
      const mockCase = {
        id: '123',
        case_name: 'Test Case',
        neutral_citation: '[2024] HKCFA 1',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCase),
      });

      const result = await getCaseDetail('123');
      expect(result).toEqual(mockCase);
    });

    it('throws error on failed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'Case not found' } }),
      });

      await expect(getCaseDetail('invalid')).rejects.toThrow('Case not found');
    });
  });

  describe('getLegislationDetail', () => {
    it('sends GET request with legislation ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: '456', title_en: 'Test Act' }),
      });

      await getLegislationDetail('456');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/legislation/456',
        expect.objectContaining({ headers: expect.any(Object) })
      );
    });

    it('throws error on failed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'Legislation not found' } }),
      });

      await expect(getLegislationDetail('invalid')).rejects.toThrow('Legislation not found');
    });
  });

  describe('getCaseCitations', () => {
    it('sends GET request with case ID for citations', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ cited_cases: [], citing_cases: [] }),
      });

      await getCaseCitations('123');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/cases/123/citations',
        expect.objectContaining({ headers: expect.any(Object) })
      );
    });

    it('returns citations response on success', async () => {
      const mockCitations = {
        cited_cases: [{ id: '1', citation_text: '[2023] HKCFI 1' }],
        citing_cases: [{ id: '2', neutral_citation: '[2024] HKCFI 2' }],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCitations),
      });

      const result = await getCaseCitations('123');
      expect(result).toEqual(mockCitations);
    });

    it('throws error on failed response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ error: { message: 'Failed to get citations' } }),
      });

      await expect(getCaseCitations('invalid')).rejects.toThrow('Failed to get citations');
    });
  });
});
