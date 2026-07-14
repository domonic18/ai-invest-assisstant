import { useQuery } from '@tanstack/react-query'

import { fetchAuctionData, type AuctionParams } from '@/api/auction'

export function useAuctionData(code: string, params: AuctionParams = {}) {
  return useQuery({
    queryKey: ['auction', code, params],
    queryFn: () => fetchAuctionData(code, params),
    enabled: code.length > 0,
  })
}
