import { useQuery, useMutation } from '@tanstack/react-query'
import { queryClient } from '../../queryClient'
import { getProject, updateProject } from '../../api/project'
import type { Project, UpdateProjectRequest } from '../../api/project'
import { listChapters, createChapter, updateChapter, deleteChapter } from '../../api/chapter'
import type { Chapter, CreateChapterRequest, UpdateChapterRequest } from '../../api/chapter'
import { getAsset, upsertAsset } from '../../api/asset'
import type { Asset, UpsertAssetRequest } from '../../api/asset'
import { listDramaEpisodes, updateEpisodeOutline, updateSourceChapters } from '../../api/drama'
import type { DramaEpisode } from '../../api/drama'

async function fetchAssetSafe(projectId: string, assetType: string): Promise<Asset> {
  try {
    return await getAsset(projectId, assetType)
  } catch (err: any) {
    if (err.response?.status === 404) {
      return {
        id: '',
        project_id: projectId,
        asset_type: assetType,
        content_text: '',
        content_json: null,
        version: 0,
        updated_at: '',
      }
    }
    throw err
  }
}

export function useProjectData(projectId: string | undefined) {
  const enabled = !!projectId
  const pid = projectId!

  // Queries
  const projectQuery = useQuery<Project, Error>({
    queryKey: ['project', pid],
    queryFn: () => getProject(pid),
    enabled,
  })

  const chaptersQuery = useQuery<Chapter[], Error>({
    queryKey: ['chapters', pid],
    queryFn: () => listChapters(pid),
    enabled,
  })

  const architectureQuery = useQuery<Asset, Error>({
    queryKey: ['asset', pid, 'architecture'],
    queryFn: () => fetchAssetSafe(pid, 'architecture'),
    enabled,
  })

  const charactersQuery = useQuery<Asset, Error>({
    queryKey: ['asset', pid, 'characters'],
    queryFn: () => fetchAssetSafe(pid, 'characters'),
    enabled,
  })

  const directoryQuery = useQuery<Asset, Error>({
    queryKey: ['asset', pid, 'directory'],
    queryFn: () => fetchAssetSafe(pid, 'directory'),
    enabled,
  })

  const dramaEpisodesQuery = useQuery<DramaEpisode[], Error>({
    queryKey: ['dramaEpisodes', pid],
    queryFn: () => listDramaEpisodes(pid),
    enabled,
  })

  // Mutations
  const saveProject = useMutation<Project, Error, UpdateProjectRequest>({
    mutationFn: (data) => updateProject(pid, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', pid] })
    },
  })

  const saveAsset = useMutation<Asset, Error, { assetType: string; data: UpsertAssetRequest }>({
    mutationFn: ({ assetType, data }) => upsertAsset(pid, assetType, data),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['asset', pid, vars.assetType] })
    },
  })

  const addChapter = useMutation<Chapter, Error, CreateChapterRequest>({
    mutationFn: (data) => createChapter(pid, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapters', pid] })
    },
  })

  const updateChapterMut = useMutation<Chapter, Error, { chapterId: string; data: UpdateChapterRequest }>({
    mutationFn: ({ chapterId, data }) => updateChapter(chapterId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapters', pid] })
    },
  })

  const deleteChapterMut = useMutation<void, Error, string>({
    mutationFn: (chapterId) => deleteChapter(chapterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chapters', pid] })
    },
  })

  const updateEpisode = useMutation<DramaEpisode, Error, { episodeId: string; outlineJson: Record<string, any> }>({
    mutationFn: ({ episodeId, outlineJson }) => updateEpisodeOutline(episodeId, outlineJson),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', pid] })
    },
  })

  const updateSource = useMutation<DramaEpisode, Error, { episodeId: string; sourceChapters: string }>({
    mutationFn: ({ episodeId, sourceChapters }) => updateSourceChapters(episodeId, sourceChapters),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', pid] })
    },
  })

  return {
    // Data
    project: projectQuery.data ?? null,
    chapters: chaptersQuery.data ?? [],
    architecture: architectureQuery.data ?? null,
    characters: charactersQuery.data ?? null,
    directory: directoryQuery.data ?? null,
    dramaEpisodes: dramaEpisodesQuery.data ?? [],
    // Loading states
    projectLoading: projectQuery.isLoading,
    chaptersLoading: chaptersQuery.isLoading,
    architectureLoading: architectureQuery.isLoading,
    charactersLoading: charactersQuery.isLoading,
    directoryLoading: directoryQuery.isLoading,
    dramaLoading: dramaEpisodesQuery.isLoading,
    // Errors
    projectError: projectQuery.error,
    // Mutations
    saveProject,
    saveAsset,
    addChapter,
    updateChapter: updateChapterMut,
    deleteChapter: deleteChapterMut,
    updateEpisode,
    updateSource,
  }
}
