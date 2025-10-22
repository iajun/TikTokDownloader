<template>
  <a-card class="favorites-container">
    <template #title>
      <div class="header">
        <span>⭐ 收藏夹</span>
      </div>
    </template>
    
    <a-layout class="favorites-layout">
      <!-- 左侧：收藏夹树 -->
      <a-layout-sider 
        :width="300" 
        theme="light" 
        class="tree-sider"
        :collapsed="collapsed"
        :collapsible="false"
        @collapse="collapsed = $event"
      >
        <div class="tree-header">
          <a-button 
            type="primary" 
            @click="showCreateFolderModal"
            :icon="h(PlusOutlined)"
            block
          >
            新建收藏夹
          </a-button>
        </div>
        <a-spin :spinning="treeLoading">
          <a-tree
            :tree-data="treeData"
            :field-names="{ children: 'children', title: 'title', key: 'key' }"
            :selected-keys="selectedKeys"
            :expanded-keys="expandedKeys"
            :draggable="true"
            @select="handleTreeSelect"
            @expand="handleTreeExpand"
            @drop="handleTreeDrop"
          >
            <template #title="{ title, key, dataRef }">
              <div class="tree-node-title">
                <span 
                  @dblclick="handleRename(key, dataRef)"
                  class="folder-name"
                >
                  {{ title }}
                </span>
                <span v-if="dataRef.task_count !== undefined" class="task-count">
                  ({{ dataRef.task_count }})
                </span>
                <a-dropdown :trigger="['contextmenu']">
                  <template #overlay>
                    <a-menu @click="(e: any) => handleTreeMenuClick(e, dataRef)">
                      <a-menu-item key="rename">
                        <EditOutlined /> 重命名
                      </a-menu-item>
                      <a-menu-item key="new-child">
                        <PlusOutlined /> 新建子文件夹
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger>
                        <DeleteOutlined /> 删除
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <span class="tree-node-actions">
                    <MoreOutlined />
                  </span>
                </a-dropdown>
              </div>
            </template>
          </a-tree>
        </a-spin>
      </a-layout-sider>
      
      <!-- 右侧：任务列表 -->
      <a-layout-content class="tasks-content">
        <div v-if="selectedFolderId">
          <div class="content-header">
            <h3>{{ selectedFolder?.name || '' }}</h3>
            <a-space>
              <a-button @click="refreshTasks">
                <template #icon>
                  <component :is="h(ReloadOutlined)" />
                </template>
                刷新
              </a-button>
            </a-space>
          </div>
          <TaskList 
            :tasks="collectionTasks" 
            @refresh="refreshTasks"
            :folder-id="selectedFolderId"
            show-remove-from-folder
          />
        </div>
        <a-empty v-else description="请从左侧选择收藏夹" />
      </a-layout-content>
    </a-layout>
    
    <!-- 创建/编辑文件夹对话框 -->
    <a-modal
      v-model:open="folderModalVisible"
      :title="editingFolder ? '编辑收藏夹' : '新建收藏夹'"
      @ok="handleFolderModalOk"
      @cancel="handleFolderModalCancel"
    >
      <a-form :model="folderForm" :label-col="{ span: 6 }">
        <a-form-item label="名称" required>
          <a-input v-model:value="folderForm.name" placeholder="请输入收藏夹名称" />
        </a-form-item>
        <a-form-item label="父文件夹">
          <a-tree-select
            v-model:value="folderForm.parent_id"
            :tree-data="treeSelectData"
            :field-names="{ label: 'title', value: 'id', children: 'children' }"
            placeholder="选择父文件夹（可选）"
            allow-clear
          />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea 
            v-model:value="folderForm.description" 
            placeholder="请输入描述（可选）"
            :rows="3"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import type { DataNode } from 'ant-design-vue/es/tree'
import {
  getCollectionTree,
  createCollectionFolder,
  updateCollectionFolder,
  deleteCollectionFolder,
  getCollectionTasks,
  type CollectionFolder,
  type CollectionTask
} from '@/api/collection'
import TaskList from '@/components/TaskList.vue'
import type { TaskStatus } from '@/api/task'

const collapsed = ref(false)
const treeLoading = ref(false)
const tasksLoading = ref(false)
const folderModalVisible = ref(false)
const selectedFolderId = ref<number | null>(null)
const selectedFolder = ref<CollectionFolder | null>(null)
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])

const folderForm = ref({
  name: '',
  parent_id: null as number | null,
  description: ''
})
const editingFolder = ref<CollectionFolder | null>(null)

const treeData = ref<DataNode[]>([])
const collectionTasks = ref<TaskStatus[]>([])

// 构建树选择器数据（排除正在编辑的文件夹及其子文件夹）
const treeSelectData = computed(() => {
  const buildTreeSelect = (folders: CollectionFolder[]): any[] => {
    return folders
      .filter(f => !editingFolder.value || f.id !== editingFolder.value.id)
      .map(f => ({
        id: f.id,
        title: f.name,
        value: f.id,
        children: f.children ? buildTreeSelect(f.children) : []
      }))
  }
  return buildTreeSelect(flattenedFolders.value.filter(f => !f.parent_id))
})

const flattenedFolders = ref<CollectionFolder[]>([])

// 将树结构转换为扁平的树数据
const buildTreeData = (folders: CollectionFolder[]): DataNode[] => {
  return folders.map(folder => ({
    key: folder.id.toString(),
    title: folder.name,
    task_count: folder.task_count || 0,
    children: folder.children ? buildTreeData(folder.children) : [],
    dataRef: folder
  }))
}

// 扁平化树结构
const flattenTree = (folders: CollectionFolder[], result: CollectionFolder[] = []) => {
  folders.forEach(folder => {
    result.push(folder)
    if (folder.children) {
      flattenTree(folder.children, result)
    }
  })
  return result
}

// 加载收藏夹树
const loadTree = async () => {
  treeLoading.value = true
  try {
    const response = await getCollectionTree()
    if (response.success) {
      treeData.value = buildTreeData(response.data)
      flattenedFolders.value = flattenTree(response.data)
      // 默认展开所有节点
      expandedKeys.value = flattenedFolders.value.map(f => f.id.toString())
      
      // 如果还没有选中节点，且有数据，默认选择第一个根节点
      if (!selectedFolderId.value && response.data && response.data.length > 0) {
        const firstFolder = response.data[0]
        if (firstFolder) {
          selectedKeys.value = [firstFolder.id.toString()]
          selectedFolderId.value = firstFolder.id
          selectedFolder.value = firstFolder
          // 加载第一个收藏夹的任务
          loadTasks()
        }
      }
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '加载收藏夹失败')
  } finally {
    treeLoading.value = false
  }
}

// 加载收藏夹任务
const loadTasks = async () => {
  if (!selectedFolderId.value) return
  
  tasksLoading.value = true
  try {
    const response = await getCollectionTasks(selectedFolderId.value, 100, 0)
    if (response.success) {
      collectionTasks.value = response.data.map((ct: CollectionTask) => ct.task).filter(Boolean)
    }
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '加载任务失败')
  } finally {
    tasksLoading.value = false
  }
}

const refreshTasks = () => {
  loadTasks()
  loadTree() // 更新任务数量
}

// 树节点选择
const handleTreeSelect = (keys: string[]) => {
  selectedKeys.value = keys
  if (keys.length > 0) {
    const folderId = parseInt(keys[0])
    selectedFolderId.value = folderId
    const folder = flattenedFolders.value.find(f => f.id === folderId)
    selectedFolder.value = folder || null
    loadTasks()
  } else {
    selectedFolderId.value = null
    selectedFolder.value = null
    collectionTasks.value = []
  }
}

// 树节点展开
const handleTreeExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

// 树节点拖拽
const handleTreeDrop = async (info: any) => {
  const { node, dragNode, dropPosition, dropToGap } = info
  const dragKey = parseInt(dragNode.key)
  const targetKey = parseInt(node.key)
  
  // 计算新的parent_id和sort_order
  let newParentId: number | null = null
  let newSortOrder = 0
  
  if (dropToGap) {
    // 放置到节点之间
    newParentId = node.dataRef.dataRef.parent_id
    newSortOrder = dropPosition < 0 ? node.dataRef.dataRef.sort_order : node.dataRef.dataRef.sort_order + 1
  } else {
    // 放置到节点内部
    newParentId = targetKey
    newSortOrder = 0
  }
  
  try {
    await updateCollectionFolder(dragKey, {
      parent_id: newParentId,
      sort_order: newSortOrder
    })
    message.success('移动成功')
    await loadTree()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '移动失败')
  }
}

// 显示创建文件夹对话框
const showCreateFolderModal = (parentId?: number) => {
  editingFolder.value = null
  folderForm.value = {
    name: '',
    parent_id: parentId || null,
    description: ''
  }
  folderModalVisible.value = true
}

// 重命名文件夹
const handleRename = (_key: string, dataRef: CollectionFolder) => {
  editingFolder.value = dataRef
  folderForm.value = {
    name: dataRef.name,
    parent_id: dataRef.parent_id,
    description: dataRef.description || ''
  }
  folderModalVisible.value = true
}

// 树菜单点击
const handleTreeMenuClick = ({ key }: { key: string }, dataRef: CollectionFolder) => {
  switch (key) {
    case 'rename':
      handleRename(dataRef.id.toString(), dataRef)
      break
    case 'new-child':
      showCreateFolderModal(dataRef.id)
      break
    case 'delete':
      Modal.confirm({
        title: '确认删除',
        content: `确定要删除收藏夹"${dataRef.name}"吗？此操作将同时删除所有子文件夹和任务关联。`,
        okType: 'danger',
        async onOk() {
          try {
            await deleteCollectionFolder(dataRef.id)
            message.success('删除成功')
            await loadTree()
            if (selectedFolderId.value === dataRef.id) {
              selectedFolderId.value = null
              selectedFolder.value = null
              collectionTasks.value = []
            }
          } catch (error: any) {
            message.error(error.response?.data?.detail || error.message || '删除失败')
          }
        }
      })
      break
  }
}

// 保存文件夹
const handleFolderModalOk = async () => {
  if (!folderForm.value.name.trim()) {
    message.warning('请输入收藏夹名称')
    return
  }
  
  // 规范化数据，确保 parent_id 是整数或 null
  const formData = {
    name: folderForm.value.name.trim(),
    parent_id: folderForm.value.parent_id ? parseInt(String(folderForm.value.parent_id)) : null,
    description: folderForm.value.description?.trim() || ''
  }
  
  try {
    if (editingFolder.value) {
      await updateCollectionFolder(editingFolder.value.id, formData)
      message.success('更新成功')
    } else {
      await createCollectionFolder(formData)
      message.success('创建成功')
    }
    folderModalVisible.value = false
    await loadTree()
  } catch (error: any) {
    message.error(error.response?.data?.detail || error.message || '操作失败')
  }
}

const handleFolderModalCancel = () => {
  folderModalVisible.value = false
  editingFolder.value = null
}

onMounted(() => {
  loadTree()
})
</script>

<style scoped>
.favorites-container {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.favorites-layout {
  height: 100%;
}

.tree-sider {
  border-right: 1px solid #e8e8e8;
  overflow: auto;
  overflow: hidden;
}

.tree-header {
  padding: 16px;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 10;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.tree-node-title {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 4px 0;
  min-height: 32px;
  transition: all 0.2s ease;
}

.folder-name {
  flex: 1;
  cursor: pointer;
  font-size: 14px;
  color: #262626;
  line-height: 1.5;
  transition: color 0.2s ease;
  word-break: break-word;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-name:hover {
  color: #1890ff;
}

.task-count {
  color: #8c8c8c;
  font-size: 12px;
  font-weight: 400;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 10px;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.tree-node-actions {
  opacity: 0;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  color: #8c8c8c;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tree-node-actions:hover {
  background: #f0f0f0;
  color: #262626;
}

.tree-node-title:hover .tree-node-actions {
  opacity: 1;
}

.tasks-content {
  padding: 16px;
  overflow: auto;
  background: #fff;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.content-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #262626;
}

/* Tree 节点样式优化 */
:deep(.ant-tree) {
  background: transparent;
  padding: 12px 8px;
}

:deep(.ant-tree-node-content-wrapper) {
  width: calc(100% - 24px);
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.2s ease;
  margin: 2px 0;
}

:deep(.ant-tree-node-content-wrapper:hover) {
  background: #f0f7ff !important;
}

:deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background: #e6f7ff !important;
  border: 1px solid #91d5ff;
}

:deep(.ant-tree-node-content-wrapper.ant-tree-node-selected .folder-name) {
  color: #1890ff;
  font-weight: 500;
}

:deep(.ant-tree-node-content-wrapper.ant-tree-node-selected .task-count) {
  background: #91d5ff;
  color: #0958d9;
}

:deep(.ant-tree-treenode) {
  padding: 2px 0;
  width: 100%;
}

:deep(.ant-tree-switcher) {
  width: 20px;
  height: 20px;
  line-height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.ant-tree-switcher-icon) {
  font-size: 12px;
  color: #8c8c8c;
}

:deep(.ant-tree-switcher-icon:hover) {
  color: #1890ff;
}

:deep(.ant-tree-iconEle) {
  width: 16px;
  height: 16px;
  line-height: 16px;
  margin-right: 4px;
}

/* 加载状态样式 */
:deep(.ant-spin-nested-loading) {
  min-height: 200px;
}

:deep(.ant-spin-container) {
  min-height: 200px;
}

/* 拖拽样式优化 */
:deep(.ant-tree-drag-icon) {
  color: #1890ff;
}

:deep(.ant-tree-drop-container) {
  border: 2px dashed #1890ff;
  background: #e6f7ff;
}
</style>

