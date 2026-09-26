import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export interface UsePaginationOptions {
  defaultPageSize?: number;
  syncWithUrl?: boolean;
}

export interface UsePaginationReturn {
  page: number;
  pageSize: number;
  totalCount: number;
  setPage: (page: number) => void;
  setTotalCount: (count: number) => void;
  handlePageChange: (newPage: number) => void;
  resetPage: () => void;
}

export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const { defaultPageSize = 20, syncWithUrl = true } = options;
  const [searchParams, setSearchParams] = useSearchParams();

  const getPageFromUrl = useCallback(() => {
    if (!syncWithUrl) return 1;
    const p = parseInt(searchParams.get('page') || '1', 10);
    return isNaN(p) || p < 1 ? 1 : p;
  }, [searchParams, syncWithUrl]);

  const getPageSizeFromUrl = useCallback(() => {
    if (!syncWithUrl) return defaultPageSize;
    const ps = parseInt(searchParams.get('page_size') || String(defaultPageSize), 10);
    return isNaN(ps) || ps < 1 ? defaultPageSize : ps;
  }, [searchParams, defaultPageSize, syncWithUrl]);

  const [page, setPageState] = useState<number>(getPageFromUrl);
  const [pageSize] = useState<number>(getPageSizeFromUrl);
  const [totalCount, setTotalCount] = useState<number>(0);

  // Sync state if URL changes externally (e.g. back/forward navigation)
  useEffect(() => {
    if (syncWithUrl) {
      const urlPage = getPageFromUrl();
      if (urlPage !== page) {
        setPageState(urlPage);
      }
    }
  }, [getPageFromUrl, page, syncWithUrl]);

  const updateUrl = useCallback((newPage: number) => {
    if (!syncWithUrl) return;
    setSearchParams(prev => {
      if (newPage === 1 && !prev.has('page')) return prev;
      const next = new URLSearchParams(prev);
      if (newPage > 1) {
        next.set('page', String(newPage));
      } else {
        next.delete('page');
      }
      return next;
    }, { replace: true });
  }, [syncWithUrl, setSearchParams]);

  const handlePageChange = useCallback((newPage: number) => {
    setPageState(newPage);
    updateUrl(newPage);
  }, [updateUrl]);

  const resetPage = useCallback(() => {
    setPageState(1);
    updateUrl(1);
  }, [updateUrl]);

  const setPage = useCallback((newPage: number) => {
    setPageState(newPage);
    updateUrl(newPage);
  }, [updateUrl]);

  return {
    page,
    pageSize,
    totalCount,
    setPage,
    setTotalCount,
    handlePageChange,
    resetPage,
  };
}
