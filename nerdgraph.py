import json
import requests
import logging
from string import Template

logger = logging.getLogger('usermig')


class GraphQL:
    def build_query(self):
        pass

    def name(self):
        pass

    def execute(self, api_key: str, finalize: bool):
        url = "https://api.newrelic.com/graphql"
        graphql = None
        try:
            query = self.build_query()
            logger.debug("Executing query {}...".format(query))
            if isinstance(query, str):
                graphql = {"query": query.replace("\n", "")}
            else:
                raise Exception("Invalid query")
        except Exception as e:
            logger.error(e)

        if finalize is False:
            logger.info("NRQL: {}".format(graphql))
            return

        headers = {"API-Key": api_key}
        client = requests.Session()
        client.headers.update(headers)

        response = client.post(url, json=graphql)
        response.raise_for_status()

        if response.status_code == requests.codes.ok:
            text = response.text
            if isinstance(text, str):
                try:
                    jsondata = json.loads(text)
                    if "errors" in jsondata:
                        logger.error("{}".format(
                            jsondata["errors"][0]["message"]))
                    else:
                        logger.debug("Response [{}]".format(text))
                    return jsondata
                except Exception as e:
                    logger.error(e)
                    raise e

class GroupsQuery(GraphQL):
    def __init__(self, auth_domain):
        self.auth_domain = auth_domain

    def build_query(self):
        return Template("""
{
  actor {
    organization {
      userManagement {
        authenticationDomains(id: "$auth_domain") {
          authenticationDomains {
            groups {
              groups {
                displayName
                id
              }
            }
          }
        }
      }
    }
  }
}
        """).substitute(self.__dict__)

    def name(self):
        return "GroupsQuery"
y

class UsersQuery(GraphQL):
    def __init__(self, auth_domain):
        self.auth_domain = auth_domain

    def build_query(self):
        return Template("""
{
  actor {
    organization {
      userManagement {
        authenticationDomains(id: "$auth_domain") {
          authenticationDomains {
            users {
              users {
                type {
                  displayName
                  id
                }
                name
                timeZone
                groups {
                  groups {
                    id
                    displayName
                  }
                }
                email
                emailVerificationState
                id
              }
              nextCursor
            }
          }
        }
      }
    }
  }
}
        """).substitute(self.__dict__)

    def name(self):
        return "UsersQuery"


class RolesQuery(GraphQL):
    def __init__(self, source_domain_id):
        self.source_domain_id = source_domain_id

    def build_query(self):
        return Template("""
{
  actor {
    organization {
      authorizationManagement {
        authenticationDomains(id: "$source_domain_id") {
          authenticationDomains {
            groups {
              groups {
                displayName
                id
                roles {
                  roles {
                    id
                    name
                    roleId
                    type
                    accountId
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
        """).substitute(self.__dict__)

    def name(self):
        return "RolesQuery"


class CreateUser(GraphQL):
    def __init__(self, email, name, user_type, auth_domain_id):
        self.email = email
        self.name = name
        self.user_type = user_type
        self.auth_domain_id = auth_domain_id

    def build_query(self):
        return Template("""
mutation {
  userManagementCreateUser(createUserOptions: {email: "$email", name: "$name", userType: $user_type, authenticationDomainId: "$auth_domain_id"})
  {createdUser {id}}
}
        """).substitute(self.__dict__)

    def name(self):
        return "CreateUser"


class CreateGroup(GraphQL):
    def __init__(self, auth_domain, group_name):
        self.auth_domain = auth_domain
        self.group_name = group_name

    def build_query(self):
        return Template("""
mutation {
  userManagementCreateGroup(
    createGroupOptions: {
      authenticationDomainId: "$auth_domain"
      displayName: "$group_name"
    }
  ) {
    group {
      displayName
      id
    }
  }
}
        """).substitute(self.__dict__)

    def name(self):
        return "CreateGroup"


class AssignRole(GraphQL):
    def __init__(self, group_id, account_id, role_id):
        self.group_id = group_id
        self.account_id = account_id
        self.role_id = role_id

    def build_query(self):
        if self.account_id:
            return Template("""
mutation {
  authorizationManagementGrantAccess(
    grantAccessOptions: {
      groupId: "$group_id"
      accountAccessGrants: {
        accountId: $account_id
        roleId: "$role_id"
      }
    }
  ) {
    roles {
      displayName
      accountId
    }
  }
}    
        """).substitute(self.__dict__)
        else:
            logger.info("Assigning organization scoped role to {}".format(self.group_id))
            return Template("""
mutation {
  authorizationManagementGrantAccess(
    grantAccessOptions: {
      organizationAccessGrants: { roleId: "$role_id" }
      groupId: "$group_id"
    }
  ) {
    roles {
      roleId
      type
      organizationId
    }
  }
}

        """).substitute(self.__dict__)

    def name(self):
        return "AssignRole"


class AddUserToGroup(GraphQL):
    def __init__(self, group_id, user_id):
        self.group_id = group_id
        self.user_id = user_id

    def build_query(self):
        return Template("""
mutation {
  userManagementAddUsersToGroups(
    addUsersToGroupsOptions: {
      groupIds: ["$group_id"]
      userIds: [$user_id]
    }
  ) {
    groups {
      displayName
      id
    }
  }
}
        """).substitute(self.__dict__)

    def name(self):
        return "AddUserToGroup"
