import request from '@/utils/request'

/**
 * 分页模糊查询实验室设备列表
 */
export function getEquipmentPageList(params) {
  return request({
    url: '/api/equipment/list',
    method: 'get',
    params
  })
}

/**
 * 新增实验室设备
 */
export function createEquipmentApi(data) {
  return request({
    url: '/api/equipment',
    method: 'post',
    data
  })
}

/**
 * 修改实验室设备
 */
export function updateEquipmentApi(equipmentId, data) {
  return request({
    url: `/api/equipment/${equipmentId}`,
    method: 'put',
    data
  })
}

/**
 * 删除实验室设备
 */
export function deleteEquipmentApi(equipmentId) {
  return request({
    url: `/api/equipment/${equipmentId}`,
    method: 'delete'
  })
}
