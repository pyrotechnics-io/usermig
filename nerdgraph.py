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

    async def execute(self, api_key: str):
        url = "https://api.newrelic.com/graphql"
        graphql = None
        try:
            query = self.build_query()
            if isinstance(query, str):
                graphql = {"query": query.replace("\n", "")}
            else:
                raise Exception("Invalid query")
        except Exception as e:
            logger.error(e)

        headers = {"API-Key": api_key}
        client = requests.Session()
        client.headers.update(headers)

        response = client.post(url, json=graphql)
        response.raise_for_status()

        if response.status_code == requests.codes.ok:
            text = response.text
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except Exception as e:
                    logger.error(e)
                    raise e


class UsersQuery(GraphQL):
    def __init__(self, auth_domain):
        self.auth_domain = auth_domain

    def build_query(self):
        return Template("""
{
  actor {
    organization {
      userManagement {
        authenticationDomains(id: "{auth_domain}") {
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
        """).substitute(self)

    def name(self):
        return "UsersQuery"


class RolesQuery(GraphQL):
    def build_query(self):
        return """
{
  actor {
    organization {
      authorizationManagement {
        authenticationDomains {
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
        """

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
  userManagementCreateUser(createUserOptions: {email: "{email}", name: "{name}", userType: {user_type}, authenticationDomainId: "{auth_domain_id}"})

}
        """).substitute(self)

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
      authenticationDomainId: "{auth_domain}"
      displayName: "{group_name}"
    }
  ) {
    group {
      displayName
      id
    }
  }
}
        """).substitute(self)

    def name(self):
        return "CreateGroup"


class AssignRole(GraphQL):
    def __init__(self, group_id, account_id, role_id):
        self.group_id = group_id
        self.account_id = account_id
        self.role_id = role_id

    def build_query(self):
        return Template("""
mutation {
  authorizationManagementGrantAccess(
    grantAccessOptions: {
      groupId: "{group_id}"
      accountAccessGrants: {
        accountId: {account_id}
        roleId: "{role_id}"
      }
    }
  ) {
    roles {
      displayName
      accountId
    }
  }
}    
        """).substitute(self)

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
      groupIds: [{group_id}]
      userIds: [{user_id}]
    }
  ) {
    groups {
      displayName
      id
    }
  }
}
        """).substitute(self)

    def name(self):
        return "AddUserToGroup"
