# 用户、角色与页面 API

## 一、说明

登录接口公开；其余接口需要有效令牌。账号管理需要 `user` 或 `user:accounts` 页面权限，角色和页面管理需要 `user` 或 `user:roles` 页面权限。

除文件流和 WebSocket 外，接口使用统一 JSON 包装：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {}
}
```

接口地址均包含应用统一前缀 `/api`。需要登录的 HTTP 接口使用
`Authorization: Bearer <JWT令牌>`；JSON 请求使用
`Content-Type: application/json`。各接口另有说明时，以接口说明为准。

## 二、API

### 登录

- 请求地址：`POST /api/user/login`

- 参数：

  | 参数名   | 类型 | 必传 | 说明 |
  | -------- | ---- | ---- | ---- |
  | account  | str  | 是   | 账号 |
  | password | str  | 是   | 密码 |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "token": "eyJhbGciOi...",
          "token_type": "Bearer",
          "expires_in": 86400,
          "user_id": "f8476aa1-a00f-43fc-a1dd-638be4b042da",
          "role_id": "f9541d84-3b0b-4c00-ae35-1b3d1dadbcfb",
          "account": "test",
          "nickname": "test",
          "page_codes": ["asset:tree", "asset:table"]
      }
  }
  ```



### 登出

- 请求地址：`POST /api/user/logout`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```



### 个人页面

- 请求地址：`GET /api/user/account/me`

- 请求头：

  | 请求头        | 值格式           |
  | ------------- | ---------------- |
  | Authorization | Bearer {JWT令牌} |

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "user_id": "2efbe873-aa25-44d7-80f3-e1bc0b376a8b",
          "account": "test",
          "nickname": "测试测试",
          "role_name": "test",
          "create_types": [
              "room",
              "sensor",
              "terminal"
          ],
          "asset_tree": [
              {
                  "asset_id": "80bee77b-52f4-4682-9b56-9b0c695e6503",
                  "name": "测试楼宇",
                  "permission": "R",
                  "sub_assets": [
                      {
                          "asset_id": "8919b3c8-092d-4854-b4db-7e916149ef8b",
                          "name": "测试楼层",
                          "permission": "R",
                          "sub_assets": [
                              {
                                  "asset_id": "2d545ff5-9253-4f6e-9a4a-f45a0bb77be6",
                                  "name": "测试房间",
                                  "permission": "RU",
                                  "sub_assets": [
                                      {
                                          "asset_id": "64dbc0dc-e359-4a0a-881a-7940e2abf244",
                                          "name": "测试终端",
                                          "permission": "RD"
                                      }
                                  ]
                              }
                          ]
                      }
                  ]
              }
          ]
      }
  }
  ```

  | 字段 | 说明 |
  |------|------|
  | create_types | 该用户可创建的资产类型列表（C 权限），root 返回全部五种 |
  | asset_tree | 按可见范围剪枝的资产树，每个节点含 `permission` 字段（R/U/D/O 组合字符串，无权限则为空串） |



### 账号管理

#### 账号分页查询

- 请求地址：`POST /api/user/account/form?page=XXX&limit=XXX`

- 参数：

  | 参数名  | 类型 | 必传 | 说明             |
  | ------- | ---- | ---- | ---------------- |
  | account | str  | 否   | 账号，模糊搜索   |
  | role_id | str  | 否   | 角色ID，精确筛选 |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "items": [
              {
                  "user_id": "62e0ce27-fb3c-42c6-ba99-598ddcd31633",
                  "account": "root",
                  "nickname": "根管理员",
                  "role_name": "root"
              }
          ],
          "total": 2
      }
  }
  ```



#### 查询账号详情

- 请求地址：`GET /api/user/account/find/{user_id}`

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "user_id": "xxx",
          "account": "root",
          "nickname": "根管理员",
          "role_id": "xxx",
          "role_name": "root",
          "asset_permissions": [
              {
                  "user_asset_id": "xxx",
                  "user_id": "xxx",
                  "asset_id": "xxx",
                  "perm_retrieve": true,
                  "perm_update": true,
                  "perm_delete": false,
                  "perm_operate": false
              }
          ]
      }
  }
  ```



#### 新增账号

- 请求地址：`POST /api/user/account/add`

- 参数：

  | 参数名   | 类型 | 必传 | 说明         |
  | -------- | ---- | ---- | ------------ |
  | account  | str  | 是   | 登录账号     |
  | password | str  | 是   | 密码         |
  | nickname | str  | 是   | 昵称         |
  | role_id  | str  | 是   | 所属角色 ID  |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "user_id": "xxx",
          "role_id": "xxx",
          "account": "test",
          "nickname": "测试用户"
      }
  }
  ```



#### 修改账号

- 请求地址：`POST /api/user/account/edit/{user_id}`

- 参数：

  | 参数名            | 类型                | 必传 | 说明                      |
  | ----------------- | ------------------- | ---- | ------------------------- |
  | account           | str                 | 是   | 登录账号                  |
  | password          | str                 | 是   | 密码                      |
  | nickname          | str                 | 是   | 昵称                      |
  | role_id           | str                 | 是   | 所属角色 ID               |
  | asset_permissions | List[AssetPermItem] | 否   | 用户资产权限列表，不传则不改动，传空列表则清空全部 |

  **AssetPermItem 结构**：

  | 参数名         | 类型 | 必传 | 说明                  |
  | -------------- | ---- | ---- | --------------------- |
  | asset_id       | str  | 是   | 资产 ID               |
  | perm_retrieve  | bool | 否   | R 查看，默认 false     |
  | perm_update    | bool | 否   | U 修改，默认 false     |
  | perm_delete    | bool | 否   | D 删除，默认 false     |
  | perm_operate   | bool | 否   | O 操作，仅终端和传感器可设为 true，默认 false |

- 说明：
  - 传 `asset_permissions` 时为全量替换（先删后建），不传则保留现有权限不变
  - 修改 role_id 时用户级 asset_permissions 保留不变
  - 新建终端或传感器时，创建者默认获得 R/U/D/O；楼宇、楼层和房间不允许配置 O
  - 即时刷新 Redis 缓存

- 返回格式：同查询账号详情

- 示例：

  ```json
  {
      "account": "test",
      "password": "123456",
      "nickname": "测试用户",
      "role_id": "xxx",
      "asset_permissions": [
          {
              "asset_id": "yyy",
              "perm_retrieve": true,
              "perm_update": true,
              "perm_delete": false,
              "perm_operate": false
          }
      ]
  }
  ```



#### 删除账号

- 请求地址：`GET /api/user/account/drop/{user_id}`

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```



#### 重置账号密码

- 请求地址：`GET /api/user/account/resetPwd/{user_id}`

- 参数：无

- 说明：重置为系统默认密码

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```



### 角色管理

#### 角色分页查询

- 请求地址：`POST /api/user/role/form?page=XXX&limit=XXX`

- 参数：

  | 参数名   | 类型 | 必传 | 说明             |
  | -------- | ---- | ---- | ---------------- |
  | name     | str  | 否   | 角色名，模糊搜索 |
  | describe | str  | 否   | 描述，模糊搜索   |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "items": [
              {
                  "role_id": "f9f60bac-9fd3-4fff-8983-2e73387337eb",
                  "name": "root",
                  "describe": "root user with all permissions"
              }
          ],
          "total": 1
      }
  }
  ```



#### 查询角色详情

- 请求地址：`GET /api/user/role/find/{user_id}`

- 路径参数：`user_id` 为角色 ID（路由沿用该参数名）。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "name": "test",
          "describe": "测试",
          "page_ids": [
              "9b68f12b-a271-4450-a34d-e38382e35091"
          ],
          "role_id": "5a02dd12-642d-4fd8-ac5e-7bd6420f8ae2",
          "page_codes": [
              "asset:tree"
          ],
          "asset_permission": {
              "part_asset_type": [
                  {
                      "type": "room",
                      "permission": "C"
                  },
                  {
                      "type": "terminal",
                      "permission": "C"
                  },
                  {
                      "type": "sensor",
                      "permission": "C"
                  }
              ],
              "part_asset_id": [
                  {
                      "asset_id": "80bee77b-52f4-4682-9b56-9b0c695e6503",
                      "name": "测试楼宇",
                      "permission": "R",
                      "sub_assets": [
                          {
                              "asset_id": "8919b3c8-092d-4854-b4db-7e916149ef8b",
                              "name": "测试楼层",
                              "permission": "R",
                              "sub_assets": [
                                  {
                                      "asset_id": "2d545ff5-9253-4f6e-9a4a-f45a0bb77be6",
                                      "name": "测试房间",
                                      "permission": "RU",
                                      "sub_assets": [
                                          {
                                              "asset_id": "64dbc0dc-e359-4a0a-881a-7940e2abf244",
                                              "name": "测试终端",
                                              "permission": "RU"
                                          }
                                      ]
                                  }
                              ]
                          }
                      ]
                  }
              ]
          }
      }
  }
  ```



#### 新增角色

- 请求地址：`POST /api/user/role/add`

- 参数：

  | 参数名           | 类型                  | 必传 | 说明               |
  | ---------------- | --------------------- | ---- | ------------------ |
  | name             | str                   | 是   | 角色名             |
  | describe         | str                   | 否   | 角色描述           |
  | page_ids         | List[str]             | 否   | 角色可访问的页面ID |
  | asset_permission | AssetPermissionSchema | 否   | 角色拥有的资产权限 |

  **asset_permission 结构**：

  | 字段            | 类型 | 说明                                       |
  | --------------- | ---- | ------------------------------------------ |
  | part_asset_type | list | 资产类型创建权限，每项：`{"type": "room", "permission": "C"}` |
  | part_asset_id   | list | 资产实例权限（平铺列表，无需子节点），每项：`{"asset_id": "xxx", "permission": "RUD"}` |

  **permission 取值**：`C`（创建）、`R`（查看）、`U`（修改）、`D`（删除）、`O`（操作，仅终端和传感器）。例如终端操作权限为 `{"asset_id": "terminal-uuid", "permission": "RO"}`。

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "role_id": "adcc7be6-8eb3-4c48-849a-f1b0fcc9c06e",
          "name": "测试",
          "describe": "testtest"
      }
  }
  ```



#### 修改角色

- 请求地址：`POST /api/user/role/edit/{user_id}`

- 路径参数：`user_id` 为角色 ID（路由沿用该参数名）。

- 请求体：同新增角色，所有字段均可选

- 说明：
  - 修改资产权限时，被移除的 R 权限会级联清理该角色下所有用户对应的 U/D/O 权限
  - 修改后实时刷新 Redis，在线用户即时生效

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "role_id": "bc80e2ba-d5eb-4be0-bf34-eaef588ee486",
          "name": "测试",
          "describe": "testtest"
      }
  }
  ```



#### 删除角色

- 请求地址：`GET /api/user/role/drop/{user_id}`

- 路径参数：`user_id` 为角色 ID（路由沿用该参数名）。无请求体。

- 说明：删除角色及关联的 role_asset / role_page。用户级 user_asset 权限保留不变，用户原有的 role_id 变为无效引用（需先迁移用户到其他角色）

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```



### 页面管理

#### 获取所有页面（树结构）

- 请求地址：`GET /api/user/page/tree`

- 参数：无

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": [
          {
              "page_id": "d8f8b153-d9e8-4fa0-81c5-3242c4020ec6",
              "page_id_parent": null,
              "name": "用户管理",
              "path_code": "user",
              "sub_pages": [
                  {
                      "page_id": "d1d63fd2-bc8e-4967-bcd6-4b4e4934ce9a",
                      "page_id_parent": "d8f8b153-d9e8-4fa0-81c5-3242c4020ec6",
                      "name": "账户管理",
                      "path_code": "user:accounts"
                  },
                  {
                      "page_id": "a36a1709-e581-402d-8950-db8c4a657ba8",
                      "page_id_parent": "d8f8b153-d9e8-4fa0-81c5-3242c4020ec6",
                      "name": "角色管理",
                      "path_code": "user:roles"
                  }
              ]
          },
          {
              "page_id": "xxx",
              "page_id_parent": null,
              "name": "资产管理",
              "path_code": "asset",
              "sub_pages": [
                  { "page_id": "xxx", "name": "资产树", "path_code": "asset:tree" },
                  { "page_id": "xxx", "name": "资产表", "path_code": "asset:table" }
              ]
          }
      ]
  }
  ```



#### 新增页面

- 请求地址：`POST /api/user/page/add`

- 参数：

  | 参数名         | 类型 | 必传 | 说明                       |
  | -------------- | ---- | ---- | -------------------------- |
  | page_id_parent | str  | 否   | 父页面ID                   |
  | name           | str  | 是   | 页面名                     |
  | path_code      | str  | 是   | 页面编码，如 `user:accounts` |

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": {
          "page_id": "xxx",
          "page_id_parent": null,
          "name": "新页面",
          "path_code": "new:page"
      }
  }
  ```



#### 删除页面

- 请求地址：`GET /api/user/page/drop/{page_id}`

- 参数：无

- 说明：父页面会级联删除所有子页面及关联的角色页面权限

- 返回格式：

  ```json
  {
      "success": true,
      "code": 200,
      "message": "请求成功",
      "data": { "ok": true }
  }
  ```
