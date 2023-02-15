import json
import requests

class GraphQL:
    def build_query(self) -> Result[str, MutationError]:
        pass

    def name(self) -> str:
        pass

    async def execute(self, api_key: str) -> Result[dict, MutationError]:
        url = "https://api.newrelic.com/graphql"
        graphql = None
        try:
            query = self.build_query()
            if isinstance(query, str):
                graphql = {"query": query.replace("\n", "")}
            else:
                raise Exception("Invalid query")
        except Exception as e:
            return Err(MutationError(e))

        headers = {"API-Key": api_key}
        client = requests.Session()
        client.headers.update(headers)

        response = client.post(url, json=graphql)
        response.raise_for_status()

        if response.status_code == requests.codes.ok:
            text = response.text
            if isinstance(text, str):
                try:
                    reply = json.loads(text)
                    return Ok(reply)
                except Exception as e:
                    return Err(MutationError(f"JSON deserialization failed for {self.name()}: \n{text}"))
        return Err(MutationError("JSON deserialization failed"))

class UsersQuery(GraphQL):
    def __init__(self, auth_domain):
        self.auth_domain = auth_domain

    def build_query(self):
        return """
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
        """.format(auth_domain=auth_domain)

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
        return """
mutation {
  userManagementCreateUser(createUserOptions: {email: "{email}", name: "{name}", userType: {user_type}, authenticationDomainId: "{auth_domain_id}"})

}
        """.format(email=email, name=name, user_type=user_type, auth_domain_id=auth_domain_id)

    def name(self):
        return "CreateUser"



class CreateGroup(GraphQL):
    def __init__(self, auth_domain, group_name):
        self.auth_domain = auth_domain
        self.group_name = group_name

    def build_query(self):
        return """
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
        """.format(auth_domain=self.auth_domain, group_name=self.group_name)

    def name(self):
        return "CreateGroup"

class AssignRole(GraphQL):
    def __init__(self, group_id, account_id, role_id):
        self.group_id = group_id
        self.account_id = account_id
        self.role_id = role_id

    def build_query(self):
        return """
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
        """.format(group_id=self.group_id, account_id=self.account_id, role_id=self.role_id)

    def name(self):
        return "AssignRole"

class AddUserToGroup(GraphQL):
    def __init__(self, group_ids, user_ids):
        self.group_ids = group_ids
        self.user_ids = user_ids

    def build_query(self):
        return """
mutation {
  userManagementAddUsersToGroups(
    addUsersToGroupsOptions: {
      groupIds: [FIRST_GROUP_ID, SECOND_GROUP_ID]
      userIds: [YOUR_USERS_IDS]
    }
  ) {
    groups {
      displayName
      id
    }
  }
}
        """

    def name(self):
        return "AddUserToGroup"