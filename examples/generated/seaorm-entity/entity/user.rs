use sea_orm::entity::prelude::*;

#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel)]
#[sea_orm(table_name = "users")]
pub struct Model {
    // OpenModels: generated = database
    #[sea_orm(primary_key, auto_increment = false, column_type = "Uuid")]
    pub id: Uuid,
    #[sea_orm(column_type = "String(StringLen::N(255))")]
    pub email: String,
    #[sea_orm(column_type = "String(StringLen::N(120))")]
    pub display_name: String,
    #[sea_orm(column_type = "String(StringLen::N(255))")]
    pub password_hash: String,
    // OpenModels: generated = database
    #[sea_orm(column_type = "TimestampWithTimeZone")]
    pub created_at: DateTimeWithTimeZone,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {
    #[sea_orm(has_many = "super::post::Entity")]
    Posts,
}

impl Related<super::post::Entity> for Entity {
    fn to() -> RelationDef {
        Relation::Posts.def()
    }
}

// OpenModels Phase 3 does not emit indexes or non-foreign-key constraints yet.
// Planned indexes:
// - users_email_key: unique [email]
// Planned constraints:
// - users_email_unique: unique [email]

impl ActiveModelBehavior for ActiveModel {}
