'use strict';
const mongoose = require('mongoose');

/**
 * users 集合：账号主体
 *
 * 设计说明：
 * - 只存登录所需的最小信息（用户名 / 密码哈希 / 注册时间），不放问卷列表。
 *   问卷归属关系放在 surveys.owner_id 上（单向引用），避免用户文档无限膨胀。
 * - username 建唯一索引，由数据库兜底保证不重名（应用层也会先查一次，给友好提示）。
 */
const userSchema = new mongoose.Schema(
  {
    username: {
      type: String,
      required: true,
      trim: true,
      minlength: 3,
      maxlength: 32,
    },
    password_hash: { type: String, required: true },
    created_at: { type: Date, default: Date.now },
  },
  { collection: 'users', versionKey: false }
);

userSchema.index({ username: 1 }, { unique: true });

// 对外输出时永远不返回 password_hash
userSchema.methods.toPublicJSON = function () {
  return { id: this._id.toString(), username: this.username, created_at: this.created_at };
};

module.exports = mongoose.model('User', userSchema);
