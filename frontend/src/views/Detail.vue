<template>
  <div class="detail-page">
    <!-- 顶部：视频详情卡片，包含详细信息和所有内容 -->
    <a-card v-if="record" class="info-card">
      <template #title>
        <div class="header">
          <div class="header-left">
            <a-button type="text" @click="$router.back()" class="back-btn">
              ← 返回
            </a-button>
            <span class="header-title">视频详情</span>
          </div>
          <div class="header-meta">
            <a-tag
              :color="getStatusColor(record.status)"
              class="status-tag"
            >
              {{ getStatusText(record.status) }}
            </a-tag>
          </div>
        </div>
      </template>

      <!-- 错误信息和重试按钮 -->
      <a-alert
        v-if="record.status === 'failed'"
        type="error"
        message="任务执行失败"
        :description="record.error_message"
        show-icon
        closable
        class="error-alert"
        style="margin-bottom: 16px"
      >
        <template #action>
          <a-button
            type="primary"
            size="small"
            @click="handleRetry"
            :loading="retryLoading"
          >
            重新执行
          </a-button>
        </template>
      </a-alert>

      <!-- 详细信息 -->
      <a-descriptions :column="2" bordered size="small" style="margin-bottom: 16px">
        <a-descriptions-item label="视频ID">{{
          record.id
        }}</a-descriptions-item>
        <a-descriptions-item label="链接">
          <a
            :href="record.url"
            target="_blank"
            style="word-break: break-all"
            >{{ record.url }}</a
          >
        </a-descriptions-item>
        <a-descriptions-item label="创建时间">{{
          formatDate(record.created_at)
        }}</a-descriptions-item>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 视频预览、语音转录、文件列表，使用折叠组件以节省空间 -->
      <a-collapse v-model:activeKey="collapseActiveKeys" :bordered="false" size="small">
          <!-- 视频预览 -->
          <a-collapse-panel
            v-if="record.video_path || record.video_url"
            key="video"
          >
            <template #header>
              <div style="display: flex; align-items: center; width: 100%">
                <span class="collapse-header">🎬 视频预览</span>
                <a-button
                  v-if="record.video_url"
                  type="link"
                  size="small"
                  @click.stop="handleRefreshUrls"
                  :loading="refreshingUrls"
                  style="margin-left: auto"
                >
                  🔄 刷新链接
                </a-button>
              </div>
            </template>
            <div class="video-container">
              <div class="video-wrapper">
                <video
                  ref="videoPlayer"
                  :key="videoUrlKey"
                  :src="getVideoUrl()"
                  controls
                  preload="metadata"
                  class="video-player"
                >
                  您的浏览器不支持视频播放
                </video>
              </div>
            </div>
          </a-collapse-panel>

          <!-- 语音转录 -->
          <a-collapse-panel key="transcription">
            <template #header>
              <div style="display: flex; align-items: center; width: 100%">
                <span class="collapse-header">📝 语音转录</span>
                <a-button
                  v-if="record.audio_path && record.status === 'completed'"
                  type="link"
                  size="small"
                  @click.stop="handleRetranscribe"
                  :loading="retranscribeLoading"
                  style="margin-left: auto"
                >
                  🔄 重新转录
                </a-button>
              </div>
            </template>
            <div class="content-box">
              <a-typography-paragraph
                v-if="record.transcription"
                :copyable="{ text: record.transcription }"
              >
                {{ record.transcription }}
              </a-typography-paragraph>
              <a-empty v-else description="暂无转录内容" />
            </div>
          </a-collapse-panel>

          <!-- 文件列表 -->
          <a-collapse-panel v-if="fileList.length > 0" key="files">
            <template #header>
              <span class="collapse-header"
                >📁 文件 ({{ fileList.length }})</span
              >
            </template>
            <a-list :data-source="fileList" :bordered="false">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a :href="item.url" target="_blank">{{ item.name }}</a>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </a-collapse-panel>
        </a-collapse>
    </a-card>

    <!-- 下方：AI总结 -->
    <a-card title="🤖 AI总结" class="summary-card" v-if="record" style="margin-top: 20px;">
      <div class="summary-container">
        <div class="summary-actions" v-if="record.audio_path">
          <a-select
            v-model:value="selectedPromptId"
            :options="promptOptions"
            style="min-width: 220px"
            placeholder="选择提示词（默认）"
            :loading="loadingPrompts"
            :allow-clear="true"
          />
          <a-button
            type="primary"
            @click="handleResummarize"
            :loading="loading"
          >
            {{ summaries.length > 0 ? "生成新总结" : "生成总结" }}
          </a-button>
          <a-button
            type="default"
            @click="openCustomPromptModal"
            style="margin-left: 8px"
          >
            🧪 自定义提示词
          </a-button>
        </div>
        
        <!-- 使用 tabs 展示多个总结 -->
        <a-tabs 
          v-model:activeKey="activeSummaryKey"
          v-if="summaries.length > 0"
          type="editable-card"
          @edit="handleTabEdit"
          @change="handleTabChange"
          class="summary-tabs"
        >
          <a-tab-pane
            v-for="summary in summaries"
            :key="summary.id.toString()"
            :tab="summary.name"
            :closable="summaries.length > 1"
          >
            <div class="summary-tab-content">
              <div class="summary-header">
                <a-space>
                  <a-button
                    type="text"
                    size="small"
                    @click="openRenameModal(summary)"
                  >
                    ✏️ 重命名
                  </a-button>
                  <a-divider type="vertical" />
                  <a-button
                    v-if="editingSummaryId !== summary.id"
                    type="text"
                    size="small"
                    @click="startEditSummary(summary)"
                  >
                    📝 编辑内容
                  </a-button>
                  <a-button
                    v-else
                    type="link"
                    size="small"
                    :loading="savingSummary"
                    @click="saveEditSummary(summary)"
                  >
                    💾 保存
                  </a-button>
                  <a-button
                    v-if="editingSummaryId === summary.id"
                    type="text"
                    size="small"
                    @click="cancelEditSummary"
                  >
                    取消
                  </a-button>
                  <a-divider type="vertical" />
                  <a-button
                    v-if="editingSummaryId !== summary.id"
                    type="text"
                    size="small"
                    @click="copySummaryAsMarkdown(summary)"
                  >
                    📄 复制为 Markdown
                  </a-button>
                  <a-button
                    v-if="editingSummaryId !== summary.id"
                    type="text"
                    size="small"
                    @click="copySummaryAsImage(summary)"
                    :loading="copyingImage"
                  >
                    📱 复制为长图片
                  </a-button>
                  <a-divider type="vertical" />
                  <a-popconfirm
                    title="确定要删除这个总结吗？"
                    @confirm="handleDeleteSummary(summary.id)"
                  >
                    <a-button
                      type="text"
                      size="small"
                      danger
                    >
                      🗑️ 删除
                    </a-button>
                  </a-popconfirm>
                </a-space>
              </div>
              <div class="summary-content" :ref="el => setSummaryContentRef(el, summary.id)">
                <template v-if="editingSummaryId === summary.id">
                  <a-textarea
                    v-model:value="editingContent"
                    :rows="14"
                    placeholder="在此编辑 Markdown 内容..."
                    style="font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;"
                  />
                </template>
                <template v-else>
                  <MarkdownRenderer :content="summary.content" />
                </template>
              </div>
              <div v-if="summary.custom_prompt && editingSummaryId !== summary.id" class="summary-footer">
                <a-tag color="blue">使用了自定义提示词</a-tag>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
        
        <a-empty v-else description="暂无总结，点击上方按钮生成" />
      </div>
    </a-card>
    
    <!-- 重命名模态框 -->
    <a-modal
      v-model:open="showRenameModal"
      title="重命名总结"
      @ok="handleRenameSummary"
      :confirm-loading="renaming"
    >
      <a-input
        v-model:value="renameInput"
        placeholder="请输入新的总结名称"
        :maxlength="50"
      />
    </a-modal>

    <a-card v-if="!record" :loading="loading" class="info-card">
      <a-empty description="加载中..." />
    </a-card>
  </div>

  <!-- 自定义提示词调试模态框 -->
  <a-modal
    v-model:open="showCustomPromptModal"
    title="🧪 自定义提示词调试"
    width="800px"
    :confirm-loading="loading"
    @ok="handleCustomPromptResummarize"
    @open="handleModalOpen"
  >
    <div class="custom-prompt-modal">
      <a-alert
        type="info"
        message="调试提示"
        description="您可以在这里自定义提示词来测试不同的AI总结效果。提示词中使用 {text} 占位符会被替换为实际的视频转录文本。"
        show-icon
        style="margin-bottom: 16px"
      />

      <a-form-item label="提示词模板">
        <a-textarea
          v-model:value="customPrompt"
          placeholder="请输入自定义提示词，使用 {text} 占位符代表视频转录文本"
          :rows="15"
          class="custom-prompt-textarea"
        />
      </a-form-item>

      <a-button @click="loadDefaultPrompt" :loading="loadingDefault"
        >加载默认提示词</a-button
      >
      <a-button
        @click="loadPromptHistory"
        :loading="loadingHistory"
        style="margin-left: 8px"
        >查看历史提示词</a-button
      >
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import { message, Modal } from "ant-design-vue";
// @ts-ignore - html2canvas types may not be available until package is installed
import html2canvas from "html2canvas";
import {
  getHistoryDetail,
  resummarizeTask,
  retranscribeTask,
  retryTask,
  refreshUrls,
  getTaskStatus,
} from "@/api/task";
import { getPromptTemplate, listPrompts, type Prompt } from "@/api/prompt";
import {
  getTaskSummaries,
  updateSummary,
  deleteSummary,
  type VideoSummary,
} from "@/api/summary";
import type { Record } from "@/api/task";
import { useRoute } from "vue-router";
import MarkdownRenderer from "@/components/MarkdownRenderer.vue";

const route = useRoute();

const loading = ref(false);
const retryLoading = ref(false);
const retranscribeLoading = ref(false);
const refreshingUrls = ref(false);
const record = ref<Record | null>(null);
const videoPlayer = ref<HTMLVideoElement | null>(null);
const videoUrlKey = ref(0);
// 稳定的媒体URL（避免状态更新时被覆盖）
const stableVideoUrl = ref<string>("");
const collapseActiveKeys = ref<string[]>([]); // 默认展开视频和转录

// 总结相关
const summaries = ref<VideoSummary[]>([]);
const activeSummaryKey = ref<string>("");
const showRenameModal = ref(false);
const renameInput = ref("");
const renaming = ref(false);
const renamingSummaryId = ref<number | null>(null);

// 自定义提示词相关
const showCustomPromptModal = ref(false);
const customPrompt = ref("");
const loadingDefault = ref(false);
const loadingHistory = ref(false);

// 提示词选择
const loadingPrompts = ref(false);
const prompts = ref<Prompt[]>([]);
const selectedPromptId = ref<number | undefined>(undefined);
const promptOptions = computed(() => {
  const opts = prompts.value.map(p => ({ label: p.name, value: p.id }));
  return [{ label: "使用默认提示词", value: undefined }, ...opts];
});

// 编辑总结内容
const editingSummaryId = ref<number | null>(null);
const editingContent = ref<string>("");
const savingSummary = ref(false);

// 复制相关
const copyingImage = ref(false);
const summaryContentRefs = ref<Map<number, HTMLElement>>(new Map());

// 设置总结内容 ref
const setSummaryContentRef = (el: any, summaryId: number) => {
  if (el && el instanceof HTMLElement) {
    summaryContentRefs.value.set(summaryId, el);
  } else {
    summaryContentRefs.value.delete(summaryId);
  }
};

const startEditSummary = (summary: VideoSummary) => {
  editingSummaryId.value = summary.id;
  editingContent.value = summary.content || "";
};

const cancelEditSummary = () => {
  editingSummaryId.value = null;
  editingContent.value = "";
};

const saveEditSummary = async (summary: VideoSummary) => {
  if (!editingSummaryId.value) return;
  const content = editingContent.value ?? "";
  savingSummary.value = true;
  try {
    const res = await updateSummary(summary.id, { content });
    if (res.success) {
      message.success("已保存总结内容");
      editingSummaryId.value = null;
      editingContent.value = "";
      await loadSummaries();
      // 保持当前tab激活
      activeSummaryKey.value = summary.id.toString();
    } else {
      message.error("保存失败");
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "保存失败");
  } finally {
    savingSummary.value = false;
  }
};

// 获取当前 video_id
const getCurrentVideoId = () => {
  return record.value?.video_id || "";
};

// 缓存键
const getCacheKey = () => {
  const videoId = getCurrentVideoId();
  return videoId ? `custom_prompt_${videoId}` : "";
};

// 从缓存加载提示词
const loadCachedPrompt = () => {
  const cacheKey = getCacheKey();
  console.log("Load cached prompt for key:", cacheKey);
  if (cacheKey) {
    const cached = localStorage.getItem(cacheKey);
    console.log("Cached value:", cached);
    if (cached) {
      customPrompt.value = cached;
      console.log("Loaded cached prompt:", customPrompt.value.substring(0, 50));
    }
  }
};

// 保存提示词到缓存
const saveCachedPrompt = () => {
  const cacheKey = getCacheKey();
  if (cacheKey && customPrompt.value) {
    localStorage.setItem(cacheKey, customPrompt.value);
  }
};

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return date.toLocaleString("zh-CN");
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "pending":
    case "downloading":
    case "extracting_audio":
    case "transcribing":
    case "summarizing":
      return "processing";
    default:
      return "default";
  }
};

const getStatusText = (status: string) => {
  const statusMap: { [key: string]: string } = {
    completed: "已完成",
    failed: "执行失败",
    pending: "等待中",
    downloading: "下载中",
    extracting_audio: "提取音频中",
    transcribing: "转文字中",
    summarizing: "AI总结中",
  };
  return statusMap[status] || status;
};

const getVideoUrl = () => {
  if (!record.value) return "";

  // 优先使用稳定的S3预签名URL
  if (stableVideoUrl.value) {
    return stableVideoUrl.value;
  }

  // 其次使用当前记录中的S3预签名URL
  if (record.value.video_url) {
    return record.value.video_url;
  }

  // 否则从video_path构造本地URL
  if (record.value.video_path) {
    return `/downloads/${record.value.video_path.split(/[\\/]/).pop()}`;
  }

  return "";
};

const loadSummaries = async () => {
  if (!record.value) return;
  
  try {
    const recordId = parseInt(route.params.recordId as string);
    const response = await getTaskSummaries(recordId);
    if (response.success && response.data) {
      summaries.value = response.data;
      // 如果当前没有激活的tab，设置第一个为激活状态
      if (summaries.value.length > 0 && !activeSummaryKey.value) {
        activeSummaryKey.value = summaries.value[0].id.toString();
      }
    }
  } catch (error: any) {
    console.error("Failed to load summaries:", error);
  }
};

const loadRecord = async () => {
  loading.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);

    // 每次进入页面时获取新的预签名URL
    const response = await refreshUrls(recordId);
    if (response.success) {
      record.value = response.data;
      // 记录稳定的URL
      stableVideoUrl.value = response.data.video_url || stableVideoUrl.value;
      // 加载总结
      await loadSummaries();

      // 如果当前任务处于进行中状态，或存在本地轮询标记，则开始轮询
      const processingStatuses = [
        "pending",
        "downloading",
        "extracting_audio",
        "transcribing",
        "summarizing",
      ];
      const shouldPollByStatus = record.value && processingStatuses.includes(record.value.status);
      const shouldPollByFlag = getPollingFlag(recordId);
      if (shouldPollByStatus || shouldPollByFlag) {
        startPolling(recordId);
      }
    }
  } catch (error: any) {
    console.error("Failed to load record:", error);
    // 如果刷新URL失败，回退到原始接口
    try {
      const recordId = parseInt(route.params.recordId as string);
      const response = await getHistoryDetail(recordId);
      if (response.success) {
        record.value = response.data;
        // 不更新稳定URL（保持之前的S3 URL）
        await loadSummaries();
        // 根据状态或本地标记决定是否开始轮询
        const processingStatuses = [
          "pending",
          "downloading",
          "extracting_audio",
          "transcribing",
          "summarizing",
        ];
        const shouldPollByStatus = record.value && processingStatuses.includes(record.value.status);
        const shouldPollByFlag = getPollingFlag(recordId);
        if (shouldPollByStatus || shouldPollByFlag) {
          startPolling(recordId);
        }
      }
    } catch (fallbackError: any) {
      message.error(fallbackError.message || "加载失败");
    }
  } finally {
    loading.value = false;
  }
};

const fileList = computed(() => {
  if (!record.value) return [];

  const files = [];

  // 视频文件
  if (record.value.video_path || record.value.video_url) {
    const url =
      record.value.video_url ||
      `/downloads/${record.value.video_path?.split(/[/\\]/).pop()}`;
    files.push({
      name: "视频文件",
      url,
    });
  }

  // 音频文件
  if (record.value.audio_path || record.value.audio_url) {
    const url =
      record.value.audio_url ||
      `/downloads/${record.value.audio_path?.split(/[/\\]/).pop()}`;
    files.push({
      name: "音频文件",
      url,
    });
  }

  // 转录文本
  if (record.value.transcription_path || record.value.transcription_url) {
    const url =
      record.value.transcription_url ||
      `/downloads/${record.value.transcription_path?.split(/[/\\]/).pop()}`;
    files.push({
      name: "转录文本",
      url,
    });
  }

  // 总结文本
  if (record.value.summary_path || record.value.summary_url) {
    const url =
      record.value.summary_url ||
      `/downloads/${record.value.summary_path?.split(/[/\\]/).pop()}`;
    files.push({
      name: "总结文本",
      url,
    });
  }

  return files;
});

const loadPrompts = async () => {
  loadingPrompts.value = true;
  try {
    const res = await listPrompts();
    if (res.success) {
      prompts.value = res.data || [];
      // 预选中默认提示词（仅显示为默认，不传 custom_prompt）
      const def = prompts.value.find(p => p.is_default === 1);
      if (def) selectedPromptId.value = undefined;
    }
  } catch (e) {
    // 忽略错误
  } finally {
    loadingPrompts.value = false;
  }
};

const handleRetranscribe = async () => {
  if (!record.value) return;

  retranscribeLoading.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);
    const response = await retranscribeTask(recordId);

    if (response.success) {
      // 立即反馈状态并开始轮询
      message.info("正在重新转录，请稍候...");
      if (record.value) {
        record.value.status = "transcribing";
        record.value.progress = 60;
      }
      // 设置轮询标记并开始轮询
      setPollingFlag(recordId, true);
      startPolling(recordId);
    } else {
      message.error("重新转录失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  } finally {
    retranscribeLoading.value = false;
  }
};

const handleResummarize = async () => {
  if (!record.value) return;

  loading.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);
    // 如果选择了特定提示词，则用其内容作为 custom_prompt，否则走默认
    let custom: string | undefined = undefined;
    if (selectedPromptId?.value) {
      const picked = prompts?.value.find(p => p.id === selectedPromptId.value);
      if (picked?.content) custom = picked.content;
    }
    const response = await resummarizeTask(recordId, custom);

    if (response.success) {
      // 立即反馈状态并开始轮询
      message.info("正在生成总结，请稍候...");
      if (record.value) {
        record.value.status = "summarizing";
        record.value.progress = 90;
      }
      // 设置轮询标记并开始轮询
      setPollingFlag(recordId, true);
      startPolling(recordId);
    } else {
      message.error("生成失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  } finally {
    loading.value = false;
  }
};

const handleRetry = async () => {
  if (!record.value) return;

  retryLoading.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);
    const response = await retryTask(recordId);

    if (response.success && response.data) {
      record.value = response.data;
      message.success("任务已重新提交，将开始处理");
    } else {
      message.error("重新执行失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  } finally {
    retryLoading.value = false;
  }
};

const handleRefreshUrls = async () => {
  if (!record.value) return;

  refreshingUrls.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);
    const response = await refreshUrls(recordId);

    if (response.success && response.data) {
      record.value = response.data;
      // 更新稳定视频URL
      if (response.data.video_url) {
        stableVideoUrl.value = response.data.video_url;
      }

      // 更新key以强制重新渲染视频
      videoUrlKey.value++;

      message.success("视频链接已刷新");
    } else {
      message.error("刷新失败");
    }
  } catch (error: any) {
    console.error("Failed to refresh URLs:", error);
    message.error(error.response?.data?.detail || error.message || "刷新失败");
  } finally {
    refreshingUrls.value = false;
  }
};

// 自定义提示词相关函数
const loadDefaultPrompt = async () => {
  loadingDefault.value = true;
  try {
    const response = await getPromptTemplate();
    if (response.success && response.data) {
      customPrompt.value = response.data.value;
      message.success("已加载默认提示词");
    }
  } catch (error: any) {
    message.error(error.message || "加载失败");
  } finally {
    loadingDefault.value = false;
  }
};

const loadPromptHistory = async () => {
  message.info("暂不支持查看历史提示词，请使用默认提示词或手动输入");
};

const openCustomPromptModal = () => {
  showCustomPromptModal.value = true;
  // 立即加载缓存
  loadCachedPrompt();
};

// 轮询标记持久化（避免刷新后丢失进行中状态）
const getPollingKey = (taskId: number) => `summarizing_task_${taskId}`;
const setPollingFlag = (taskId: number, value: boolean) => {
  try {
    if (value) localStorage.setItem(getPollingKey(taskId), "1");
    else localStorage.removeItem(getPollingKey(taskId));
  } catch {}
};
const getPollingFlag = (taskId: number) => {
  try {
    return !!localStorage.getItem(getPollingKey(taskId));
  } catch {
    return false;
  }
};

let pollingInterval: number | null = null;

const startPolling = (recordId: number) => {
  // 设置轮询标记
  setPollingFlag(recordId, true);
  // 清除之前的轮询
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }

  // 保存当前的视频相关 URL，避免轮询时刷新
  const preservedUrls = {
    video_url: stableVideoUrl.value || record.value?.video_url,
    audio_url: record.value?.audio_url,
    transcription_url: record.value?.transcription_url,
  };

  pollingInterval = window.setInterval(async () => {
    try {
      const response = await getTaskStatus(recordId);
      if (response.success && response.data) {
        // 保留原有的 S3 预签名 URL，避免刷新
        let previousStatus = "";
        if (record.value) {
          previousStatus = record.value.status;
          const newStatus = response.data.status;
          const newSummary = response.data.summary;
          const newTranscription = response.data.transcription;

          // 更新状态、总结内容和转录内容
          record.value.status = newStatus;
          record.value.summary = newSummary;
          record.value.transcription = newTranscription;
          record.value.progress = response.data.progress;

          // 保留视频相关 URL，避免轮询时刷新影响视频播放
          if (preservedUrls.video_url) {
            stableVideoUrl.value = preservedUrls.video_url;
          }
          if (preservedUrls.audio_url) {
            record.value.audio_url = preservedUrls.audio_url;
          }
          if (preservedUrls.transcription_url) {
            record.value.transcription_url = preservedUrls.transcription_url;
          }
        }

        // 如果状态不是处理中，停止轮询
        if (
          response.data.status === "completed" ||
          response.data.status === "failed"
        ) {
          stopPolling();

          // 清除轮询标记
          setPollingFlag(recordId, false);

          if (response.data.status === "completed") {
            // 根据之前的状态判断是总结还是转录完成
            if (previousStatus === "transcribing") {
              message.success("转录完成");
              // 重新加载详情以获取最新的转录内容
              await loadRecord();
            } else {
              message.success("总结生成完成");
              // 重新加载总结列表
              await loadSummaries();
            }
          } else {
            // 根据之前的状态判断失败类型
            if (previousStatus === "transcribing") {
              message.error("转录失败");
            } else {
              message.error("总结生成失败");
            }
          }
        }
      }
    } catch (error: any) {
      console.error("Polling error:", error);
    }
  }, 2000); // 每2秒轮询一次
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

const handleCustomPromptResummarize = async () => {
  if (!record.value || !customPrompt.value.trim()) {
    message.warning("请输入提示词");
    return;
  }

  loading.value = true;
  try {
    const recordId = parseInt(route.params.recordId as string);
    const response = await resummarizeTask(recordId, customPrompt.value);

    if (response.success) {
      showCustomPromptModal.value = false;
      message.info("正在重新生成总结，请稍候...");

      // 保存到缓存
      saveCachedPrompt();

      // 开始轮询状态
      startPolling(recordId);
    } else {
      message.error("生成失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  } finally {
    loading.value = false;
  }
};

// 在组件卸载时清除轮询
onUnmounted(() => {
  stopPolling();
});

// 监听模态框打开事件（备用）
const handleModalOpen = () => {
  loadCachedPrompt();
};

// Tab相关处理函数
const handleTabChange = (key: string) => {
  activeSummaryKey.value = key;
};

const handleTabEdit = (targetKey: string, action: 'add' | 'remove') => {
  if (action === 'remove') {
    const summaryId = parseInt(targetKey);
    // 查找要删除的总结信息用于提示
    const summaryToDelete = summaries.value.find(s => s.id === summaryId);
    const summaryName = summaryToDelete ? summaryToDelete.name : '这个总结';
    
    // 二次确认
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除"${summaryName}"吗？此操作不可恢复。`,
      okText: '确定删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        handleDeleteSummary(summaryId);
      },
    });
  }
};

// 重命名总结
const openRenameModal = (summary: VideoSummary) => {
  renamingSummaryId.value = summary.id;
  renameInput.value = summary.name;
  showRenameModal.value = true;
};

const handleRenameSummary = async () => {
  if (!renamingSummaryId.value || !renameInput.value.trim()) {
    message.warning("请输入总结名称");
    return;
  }

  renaming.value = true;
  try {
    const response = await updateSummary(renamingSummaryId.value, {
      name: renameInput.value.trim(),
    });

    if (response.success) {
      message.success("重命名成功");
      showRenameModal.value = false;
      await loadSummaries();
    } else {
      message.error("重命名失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  } finally {
    renaming.value = false;
  }
};

// 删除总结
const handleDeleteSummary = async (summaryId: number) => {
  try {
    const response = await deleteSummary(summaryId);
    if (response.success) {
      message.success("删除成功");
      // 重新加载总结列表
      await loadSummaries();
      // 如果删除的是当前激活的tab，切换到第一个
      if (activeSummaryKey.value === summaryId.toString()) {
        if (summaries.value.length > 0) {
          activeSummaryKey.value = summaries.value[0].id.toString();
        } else {
          activeSummaryKey.value = "";
        }
      }
    } else {
      message.error("删除失败");
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || "操作失败");
  }
};

// 复制总结为 Markdown
const copySummaryAsMarkdown = async (summary: VideoSummary) => {
  try {
    const markdown = summary.content || "";
    if (!markdown.trim()) {
      message.warning("总结内容为空");
      return;
    }
    
    await navigator.clipboard.writeText(markdown);
    message.success("Markdown 已复制到剪切板");
  } catch (error: any) {
    message.error("复制失败：" + (error.message || "未知错误"));
  }
};

// 复制总结为长图片（手机长图）
const copySummaryAsImage = async (summary: VideoSummary) => {
  const contentElement = summaryContentRefs.value.get(summary.id);
  if (!contentElement) {
    message.error("未找到总结内容");
    return;
  }

  copyingImage.value = true;
  try {
    // 等待 DOM 更新完成
    await nextTick();
    await new Promise(resolve => setTimeout(resolve, 100)); // 等待渲染完成

    // 获取元素的样式信息
    const styles = window.getComputedStyle(contentElement);
    
    // 手机端宽度（375px 是常见的手机屏幕宽度）
    const mobileWidth = 425;
    
    // 克隆元素以避免修改原始元素
    const clone = contentElement.cloneNode(true) as HTMLElement;
    
    // 创建一个临时的容器用于渲染
    const tempContainer = document.createElement('div');
    tempContainer.style.cssText = `
      position: fixed;
      left: -9999px;
      top: 0;
      width: ${mobileWidth}px;
      background: ${styles.backgroundColor || '#ffffff'};
      font-family: ${styles.fontFamily || 'system-ui, -apple-system, sans-serif'};
      font-size: ${styles.fontSize || '16px'};
      line-height: ${styles.lineHeight || '1.6'};
      color: ${styles.color || '#333333'};
      padding: ${styles.padding || '20px'};
      box-sizing: border-box;
      overflow: visible;
    `;
    
    // 设置克隆元素的样式
    clone.style.cssText = `
      width: 100% !important;
      max-width: 100% !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      box-shadow: none !important;
      background: transparent !important;
    `;
    
    // 为临时容器添加 ID 以便在 onclone 中查找
    const cloneId = `temp-${Date.now()}`;
    tempContainer.setAttribute('data-clone-id', cloneId);
    
    tempContainer.appendChild(clone);
    document.body.appendChild(tempContainer);
    
    // 等待渲染完成
    await nextTick();
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // 使用 html2canvas 将 DOM 转换为 canvas
    const canvas = await html2canvas(tempContainer, {
      width: mobileWidth,
      height: tempContainer.scrollHeight,
      scale: 2, // 2x 用于更好的清晰度
      backgroundColor: '#ffffff',
      useCORS: true,
      allowTaint: true,
      logging: false,
      onclone: (clonedDoc: Document) => {
        // 确保克隆的文档中所有图片都已加载
        const clonedContainer = clonedDoc.querySelector(`[data-clone-id="${cloneId}"]`);
        if (clonedContainer) {
          const images = clonedContainer.querySelectorAll('img');
          return Promise.all(
            Array.from(images).map((img) => {
              return new Promise<void>((resolve) => {
                if ((img as HTMLImageElement).complete) {
                  resolve();
                } else {
                  (img as HTMLImageElement).onload = () => resolve();
                  (img as HTMLImageElement).onerror = () => resolve();
                }
              });
            })
          );
        }
      }
    });
    
    // 转换为 blob 并复制到剪切板
    canvas.toBlob((blob: Blob | null) => {
      // 清理临时容器
      if (document.body.contains(tempContainer)) {
        document.body.removeChild(tempContainer);
      }
      if (!blob) {
        message.error('无法创建图片');
        return;
      }
      
      navigator.clipboard.write([
        new ClipboardItem({
          'image/png': blob
        })
      ]).then(() => {
        message.success("长图片已复制到剪切板");
      }).catch((error: any) => {
        console.error('Failed to copy image:', error);
        message.error("复制失败：" + (error.message || "未知错误"));
      });
    }, 'image/png', 0.95);
    
  } catch (error: any) {
    console.error('Failed to copy summary as image:', error);
    message.error("复制失败：" + (error.message || "未知错误"));
  } finally {
    copyingImage.value = false;
  }
};

onMounted(() => {
  loadRecord();
  loadPrompts();
});
</script>

<style scoped>
.detail-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  padding: 0;
  height: auto;
  font-size: 14px;
  color: #666;
}

.back-btn:hover {
  color: #1890ff;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-tag {
  margin: 0;
}

:deep(.info-card),
:deep(.summary-card) {
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
}

:deep(.info-card .ant-card-head),
:deep(.summary-card .ant-card-head) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 16px 20px;
  min-height: auto;
}

:deep(.info-card .ant-card-body),
:deep(.summary-card .ant-card-body) {
  padding: 20px;
}

/* 折叠组件样式优化，更紧凑 */
:deep(.info-card .ant-collapse) {
  background: transparent;
  border: none;
}

:deep(.info-card .ant-collapse-item) {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
}

:deep(.info-card .ant-collapse-item:last-child) {
  margin-bottom: 0;
}

:deep(.info-card .ant-collapse-header) {
  padding: 8px 12px !important;
  min-height: auto;
}

:deep(.info-card .ant-collapse-content) {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

:deep(.info-card .ant-collapse-content-box) {
  padding: 12px !important;
}

.collapse-header {
  font-weight: 500;
  font-size: 14px;
}

.content-box {
  padding: 12px;
  background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
  border-radius: 6px;
  border: 1px solid #f0f0f0;
  max-height: 400px;
  overflow-y: auto;
}

.content-box .ant-typography {
  white-space: pre-wrap;
  word-break: break-word;
}

.summary-container {
  min-height: 300px;
}

.summary-actions {
  margin-bottom: 20px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-content {
  background: linear-gradient(135deg, #fafafa 0%, #ffffff 100%);
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  line-height: 1.8;
}

.summary-content :deep(p) {
  margin-bottom: 12px;
}

.summary-content :deep(h1),
.summary-content :deep(h2),
.summary-content :deep(h3) {
  margin-top: 20px;
  margin-bottom: 12px;
  font-weight: 600;
}

.summary-content :deep(ul),
.summary-content :deep(ol) {
  margin-bottom: 12px;
  padding-left: 24px;
}

.summary-content :deep(li) {
  margin-bottom: 6px;
}

.video-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.video-header {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}

.video-wrapper {
  max-height: 400px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
}

.video-player {
  width: 100%;
  max-width: 100%;
  max-height: 400px;
  display: block;
  outline: none;
}

.error-alert {
  margin-bottom: 16px;
}

.error-alert :deep(.ant-alert-content) {
  flex: 1;
}

.error-alert :deep(.ant-alert-action) {
  margin-left: auto;
}

:deep(.ant-descriptions-bordered) {
  border-radius: 8px;
  overflow: hidden;
}

/* 响应式优化 */
@media (max-width: 768px) {
  .detail-page {
    padding: 8px;
  }


  :deep(.info-card .ant-card-body),
  :deep(.summary-card .ant-card-body) {
    padding: 16px;
  }

  .summary-content {
    padding: 16px;
  }

  .summary-actions {
    flex-direction: column;
  }

  .summary-actions .ant-btn {
    width: 100%;
    margin-left: 0 !important;
  }
}

.custom-prompt-modal {
  padding: 8px 0;
}

.custom-prompt-textarea {
  font-family: "Monaco", "Menlo", "Ubuntu Mono", monospace;
  font-size: 13px;
}

.custom-prompt-modal :deep(.ant-form-item-label) {
  padding-bottom: 8px;
}

/* 总结tabs样式 */
.summary-tabs {
  margin-top: 16px;
}

.summary-content {
  max-width: 800px;
  margin: 0 auto;
}

.summary-tab-content {
  padding: 16px 0;
}

.summary-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.summary-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.summary-content :deep(textarea.ant-input) {
  font-size: 13px;
}
</style>
