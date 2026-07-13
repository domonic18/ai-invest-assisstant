import { useMutation } from '@tanstack/react-query'

import { analyzeChain } from '@/api/chain'

export function useChainAnalysis() {
  return useMutation({
    mutationFn: analyzeChain,
  })
}
